import logging
from time import monotonic
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.errors import GenerationError
from app.ai.provider import get_provider
from app.ai.schemas import LegalGenerationInput, LegalGenerationResult
from app.core.config import Settings
from app.db.models import Generation, utcnow
from app.services.question_service import get_question

logger = logging.getLogger(__name__)

def get_generation(db: Session, generation_id: UUID) -> Generation:
    generation = db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(404, "Generation not found")
    return generation

def generation_http_status(generation: Generation) -> int:
    if generation.status != "failed":
        return 201
    return {
        "configuration": 503, "authentication": 503, "model_unavailable": 503,
        "invalid_request": 503, "rate_limited": 429, "timeout": 504,
        "provider_unavailable": 503,
    }.get(generation.error_category, 502)

def generate_answer(db: Session, question_id: UUID, settings: Settings) -> Generation:
    question = get_question(db, question_id)
    # No title/difficulty, reference fields, or evaluations enter the model boundary.
    public_input = LegalGenerationInput(
        question_id=question.id, question_text=question.question_text,
        domain=question.domain, jurisdiction=question.jurisdiction,
        relevant_law_date=question.relevant_law_date, scenario_facts=question.scenario_facts,
    )
    model_name = {
        "mock": "mock-legal-v2", "gemini": settings.gemini_model, "openai": settings.openai_model,
    }[settings.ai_provider]
    generation = Generation(
        question_id=question.id, provider=settings.ai_provider,
        model_name=model_name, prompt_version=settings.ai_prompt_version,
        generation_metadata={"simulated": settings.ai_provider == "mock", "citations_verified": False},
    )
    try:
        db.add(generation)
        db.commit()
        db.refresh(generation)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Database unavailable; no model request was made.") from None

    generation_id = generation.id
    start = monotonic()
    try:
        provider = get_provider(settings)
        generation.provider = provider.provider
        generation.model_name = provider.model_name
        # Validate at the service boundary even when injecting a provider in tests.
        result = LegalGenerationResult.model_validate(provider.generate(public_input))
        if result.provider != provider.provider or result.model_name != provider.model_name:
            raise GenerationError("invalid_output", "Provider returned inconsistent model metadata.")
        if result.prompt_version != settings.ai_prompt_version:
            raise GenerationError("invalid_output", "Provider returned inconsistent prompt metadata.")
        generation.ai_answer = result.readable_answer
        generation.structured_answer = result.structured_answer.model_dump(mode="json")
        generation.generation_metadata = result.generation_metadata
        generation.status = "completed"
    except GenerationError as error:
        generation.status = "failed"
        generation.error_category = error.category
        generation.error_message = error.message
    except Exception:
        # No raw error, scenario, credentials or provider response enters logs.
        generation.status = "failed"
        generation.error_category = "provider_error"
        generation.error_message = "AI generation failed unexpectedly. Check provider configuration and retry."

    generation.completed_at = utcnow()
    generation.generation_metadata = {
        **(generation.generation_metadata or {}), "duration_ms": round((monotonic() - start) * 1000),
    }
    try:
        db.commit()
        db.refresh(generation)
    except SQLAlchemyError:
        db.rollback()
        # The original pending record was committed before the provider call.
        # Attempt to record persistence failure; never report unsaved output as success.
        try:
            pending = db.get(Generation, generation_id)
            if pending is not None and pending.status == "pending":
                pending.status = "failed"
                pending.error_category = "persistence"
                pending.error_message = "Could not persist model output; no answer was saved."
                pending.completed_at = utcnow()
                db.commit()
        except SQLAlchemyError:
            db.rollback()
        raise HTTPException(503, {
            "message": "Could not persist generation. Retrieve the generation status before retrying.",
            "generation_id": str(generation_id),
        }) from None
    logger.info(
        "generation_id=%s provider=%s model=%s status=%s error_category=%s duration_ms=%s response_id=%s",
        generation.id, generation.provider, generation.model_name, generation.status,
        generation.error_category, generation.generation_metadata["duration_ms"],
        generation.generation_metadata.get("response_id"),
    )
    return generation

