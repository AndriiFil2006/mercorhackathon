from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Question
from app.schemas.questions import QuestionCreate, Difficulty
def get_question(db: Session, question_id: UUID) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(404, "Question not found")
    return question
def create_question(db: Session, data: QuestionCreate) -> Question:
    question = Question(**data.model_dump(mode="json", exclude={"relevant_law_date"}), relevant_law_date=data.relevant_law_date)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question
def list_questions(db: Session, domain: str | None, difficulty: Difficulty | None, offset: int, limit: int):
    statement = select(Question)
    if domain is not None:
        statement = statement.where(Question.domain == domain)
    if difficulty is not None:
        statement = statement.where(Question.difficulty == difficulty.value)
    return db.scalars(statement.order_by(Question.created_at, Question.id).offset(offset).limit(limit)).all()

