"""Connected application API, alongside unchanged /api/v1 benchmark endpoints."""

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from app.ai.context_chat import context_reply
from app.ai.errors import GenerationError
from app.core.config import Settings, get_settings
from app.db.models import AutomatedReview, LegalHandoff, utcnow
from app.db.session import get_db
from app.research.prompts import LAWYER_SYSTEM, SCORER_SYSTEM
from app.research.service import review as make_review, aggregate
from app.schemas.chat import (
    AnswerRequest,
    ReviewRequest,
    ScorerChatRequest,
    HandoffRequest,
    LawyerRequest,
    TokenRequest,
)
from app.schemas.questions import QuestionCreate
from app.services.question_service import create_question
from app.services.generation_service import (
    generate_answer,
    get_generation,
    generation_http_status,
)

router = APIRouter(prefix="/api/legal", tags=["Connected chat and research"])


def require_consent(consented: bool):
    if not consented:
        raise HTTPException(
            403,
            "Please consent to external AI processing and public legal research before continuing.",
        )


def provider_error(error: GenerationError):
    raise HTTPException(
        error.http_status, {"message": error.message, "category": error.category}
    ) from None


def check_size(data: dict, settings: Settings):
    if len(json.dumps(data, ensure_ascii=False)) > settings.chat_context_max_chars:
        raise HTTPException(
            413,
            "Complete conversation/context is too large. Nothing was silently truncated. Start a new inquiry or adjust the configured budget.",
        )


@router.get("/config")
def config(settings: Settings = Depends(get_settings)):
    return {
        "answerProvider": settings.ai_provider,
        "answerModel": (
            settings.gemini_model
            if settings.ai_provider == "gemini"
            else settings.ai_provider
        ),
        "reviewMode": settings.review_mode,
        "reviewModels": [
            settings.review_model_authority,
            settings.review_model_jurisdiction,
            settings.review_model_reasoning,
        ],
        "hasGeminiKey": bool(settings.gemini_api_key),
        "hasGroqKey": bool(settings.groq_api_key),
        "hasSearchKey": bool(settings.tavily_api_key),
    }


@router.post("/answer")
def answer(
    request: AnswerRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    require_consent(request.external_consent)
    history = [m.model_dump(exclude={"id"}) for m in request.messages]
    facts = (
        json.dumps({"previous_conversation_untrusted": history}, ensure_ascii=False)
        if history
        else None
    )
    if facts and len(facts) > 50000:
        raise HTTPException(
            413,
            "Complete inquiry history exceeds the generation budget. No earlier messages were dropped; start a new inquiry.",
        )
    question = create_question(
        db,
        QuestionCreate(
            title=request.question[:250],
            question_text=request.question,
            domain="General legal inquiry",
            jurisdiction=request.jurisdiction,
            relevant_law_date=request.law_date,
            scenario_facts=facts,
            difficulty="medium",
        ),
    )
    result = generate_answer(db, question.id, settings)
    if result.status != "completed":
        raise HTTPException(
            generation_http_status(result),
            {
                "message": result.error_message or "Main AI generation failed.",
                "category": result.error_category,
                "generationId": str(result.id),
            },
        )
    return {
        "answer": result.ai_answer,
        "generationId": str(result.id),
        "model": result.model_name,
        "mode": (
            "mock" if (result.generation_metadata or {}).get("simulated") else "live"
        ),
        "citationsVerified": False,
    }


@router.post("/review")
def review(
    request: ReviewRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    require_consent(request.external_consent)
    if request.generation_id:
        generation = get_generation(db, request.generation_id)
        if generation.status != "completed":
            raise HTTPException(409, "Only a completed main-AI answer can be reviewed.")
        question = generation.question
        # Fetch the stored main answer; never trust an edited client copy when an ID exists.
        public = {
            "question": question.question_text,
            "answer": generation.ai_answer,
            "jurisdiction": question.jurisdiction,
            "law_date": question.relevant_law_date.isoformat(),
            "conversation_context": question.scenario_facts,
        }
        if (generation.generation_metadata or {}).get(
            "simulated"
        ) and settings.review_mode == "live":
            raise HTTPException(
                409,
                "This answer was generated in mock mode. Generate a new live answer before live legal evaluation.",
            )
        provenance = "stored_main_ai_generation"
    else:
        public = {
            "question": request.question,
            "answer": request.answer,
            "jurisdiction": request.jurisdiction,
            "law_date": request.law_date.isoformat(),
        }
        provenance = "client_supplied_answer"
    try:
        return make_review(settings, db, request, public, provenance)
    except GenerationError as error:
        provider_error(error)


@router.post("/review-chat")
def review_chat(
    request: ScorerChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    require_consent(request.external_consent)
    reports = []
    for candidate in request.reviews:
        value = candidate.get("reportId")
        if not value:
            continue
        try:
            report = db.get(AutomatedReview, UUID(value))
        except (ValueError, TypeError):
            raise HTTPException(422, "Invalid report ID") from None
        if report:
            reports.append(report.report)
    if not reports:
        raise HTTPException(
            409,
            "Complete or retry at least one backend review before asking the assessment team.",
        )
    # Recover answer/context for generation-linked audits instead of accepting altered text.
    ids = {r.get("generationId") for r in reports}
    if len(ids) > 1:
        raise HTTPException(422, "Scorer reports must belong to the same answer.")
    public = {
        "question": request.question,
        "answer": request.answer,
        "jurisdiction": request.jurisdiction,
        "law_date": request.law_date.isoformat(),
    }
    if len({r.get("answerHash") for r in reports}) > 1:
        raise HTTPException(422, "Scorer reports must belong to the same answer.")
    generation_id = next(iter(ids))
    if (
        generation_id is None
        and reports[0].get("answerHash")
        != hashlib.sha256(request.answer.encode()).hexdigest()
    ):
        raise HTTPException(422, "Scorer reports do not match this supplied answer.")
    if generation_id:
        generation = get_generation(db, UUID(generation_id))
        public = {
            "question": generation.question.question_text,
            "answer": generation.ai_answer,
            "jurisdiction": generation.question.jurisdiction,
            "law_date": generation.question.relevant_law_date.isoformat(),
        }
    context = {
        **public,
        "reports": reports,
        "aggregate": aggregate(reports),
        "history": [m.model_dump(exclude={"id"}) for m in request.history],
        "prompt": request.prompt,
    }
    try:
        return context_reply(settings, SCORER_SYSTEM, context)
    except GenerationError as error:
        provider_error(error)


@router.post("/handoff", status_code=201)
def handoff(
    request: HandoffRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    require_consent(request.consent_processing)
    if request.context is not None and not request.consent_share_context:
        raise HTTPException(
            403,
            "Explicit consent to share the full inquiry and reviewer snapshot is required.",
        )
    snapshot = (
        request.context.model_dump(mode="json", by_alias=True)
        if request.context
        else None
    )
    check_size({"snapshot": snapshot}, settings)
    token = secrets.token_urlsafe(40)
    record = LegalHandoff(
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        consent_processing=True,
        consent_share_context=request.consent_share_context,
        context_snapshot=snapshot,
        messages=[],
        state="active",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "handoffToken": token,
        "handoffId": str(record.id),
        "consentedAt": record.created_at.isoformat(),
        "contextShared": snapshot is not None,
        "identity": "ai_legal_assistant",
        "realLawyer": False,
    }


def get_handoff(token: str, db: Session) -> LegalHandoff:
    record = db.scalar(
        select(LegalHandoff).where(
            LegalHandoff.token_hash == hashlib.sha256(token.encode()).hexdigest()
        )
    )
    if not record:
        raise HTTPException(
            404, "Conversation is unavailable. Create a new consented connection."
        )
    return record


@router.post("/lawyer-chat")
def lawyer_chat(
    request: LawyerRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    record = get_handoff(request.handoff_token, db)
    if record.state != "active":
        raise HTTPException(
            410,
            "This conversation has ended or consent was revoked. Create a new connection to continue.",
        )
    if not record.consent_processing or (
        record.context_snapshot is not None and not record.consent_share_context
    ):
        raise HTTPException(403, "A valid consented handoff is required.")
    now = utcnow()
    # Atomic lease prevents simultaneous messages from overwriting conversation history.
    acquired = db.execute(
        update(LegalHandoff)
        .where(
            LegalHandoff.id == record.id,
            LegalHandoff.state == "active",
            or_(LegalHandoff.busy_until == None, LegalHandoff.busy_until < now),
        )
        .values(busy_until=now + timedelta(minutes=5))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    if acquired.rowcount != 1:
        raise HTTPException(
            409,
            "The AI legal assistant is still responding. Wait before sending another message.",
        )
    try:
        db.refresh(record)
        context = {
            "identity": "AI legal assistant, not a real lawyer",
            "consented_inquiry_snapshot": record.context_snapshot,
            "conversation": record.messages,
            "message": request.message,
        }
        check_size(context, settings)
        reply = context_reply(settings, LAWYER_SYSTEM, context)
        db.refresh(record)
        if record.state != "active":
            raise HTTPException(
                410,
                "Consent was revoked or the conversation ended while the request was in progress. The response was discarded.",
            )
        record.messages = [
            *record.messages,
            {"role": "user", "text": request.message},
            {"role": "assistant", "text": reply["answer"]},
        ]
        db.commit()
        return {
            **reply,
            "identity": "ai_legal_assistant",
            "realLawyer": False,
            "contextShared": record.context_snapshot is not None,
        }
    except GenerationError as error:
        provider_error(error)
    finally:
        db.execute(
            update(LegalHandoff)
            .where(LegalHandoff.id == record.id)
            .values(busy_until=None)
        )
        db.commit()


@router.post("/handoff/revoke")
def revoke(request: TokenRequest, db: Session = Depends(get_db)):
    record = get_handoff(request.handoff_token, db)
    record.state = "revoked"
    record.revoked_at = utcnow()
    record.context_snapshot = None
    db.commit()
    return {
        "revoked": True,
        "message": "Future processing is blocked and the stored shared snapshot was removed. Previously processed information cannot be recalled from providers.",
    }


@router.post("/handoff/close")
def close(request: TokenRequest, db: Session = Depends(get_db)):
    record = get_handoff(request.handoff_token, db)
    if record.state == "active":
        record.state = "closed"
        db.commit()
    return {"closed": True}
