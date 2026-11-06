from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Evaluation, utcnow
from app.schemas.evaluations import EvaluationCreate
from app.services.generation_service import get_generation
def create_evaluation(db: Session, data: EvaluationCreate) -> Evaluation:
    generation = get_generation(db, data.generation_id)
    if generation.question_id != data.question_id:
        raise HTTPException(422, "question_id does not match generation")
    if generation.status != "completed":
        raise HTTPException(409, "Only completed generations may be evaluated")
    evaluation = Evaluation(**data.model_dump(mode="json", exclude={"question_id", "generation_id"}),
                            independent_answer_received_at=utcnow() if data.independent_expert_answer else None,
                            question_id=data.question_id, generation_id=data.generation_id)
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation
def list_evaluations(db: Session, offset: int, limit: int):
    return db.scalars(select(Evaluation).order_by(Evaluation.created_at, Evaluation.id).offset(offset).limit(limit)).all()
def get_evaluation(db: Session, evaluation_id: UUID) -> Evaluation:
    evaluation = db.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise HTTPException(404, "Evaluation not found")
    return evaluation

