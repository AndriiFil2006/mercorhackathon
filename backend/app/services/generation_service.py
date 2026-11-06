from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.ai.provider import get_provider
from app.ai.prompts import PROMPT_VERSION
from app.core.config import Settings
from app.db.models import Generation
from app.schemas.questions import PublicQuestionInput
from app.services.question_service import get_question
def get_generation(db: Session, generation_id: UUID) -> Generation:
    generation = db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(404, "Generation not found")
    return generation
def generate_answer(db: Session, question_id: UUID, settings: Settings) -> Generation:
    question = get_question(db, question_id)
    # Explicit allowlist prevents references crossing the provider boundary.
    public_input = PublicQuestionInput(**{name: getattr(question, name) for name in PublicQuestionInput.model_fields})
    provider = get_provider(settings)
    generation = Generation(question_id=question.id, model_name=provider.model_name, prompt_version=PROMPT_VERSION)
    db.add(generation)
    db.commit()
    try:
        generation.ai_answer = provider.generate(public_input)
        generation.status = "completed"
    except Exception:
        generation.status = "failed"
        generation.error_message = "AI provider failed to generate an answer."
    db.commit()
    db.refresh(generation)
    return generation

