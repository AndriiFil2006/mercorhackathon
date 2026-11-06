from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.questions import QuestionCreate, QuestionPublic, Difficulty
from app.services import question_service
router = APIRouter(prefix="/questions", tags=["questions"])
@router.post("", response_model=QuestionPublic, status_code=201)
def create_question(data: QuestionCreate, db: Session = Depends(get_db)):
    return question_service.create_question(db, data)
@router.get("", response_model=list[QuestionPublic])
def list_questions(domain: str | None = None, difficulty: Difficulty | None = None,
                   offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                   db: Session = Depends(get_db)):
    return question_service.list_questions(db, domain, difficulty, offset, limit)
@router.get("/{question_id}", response_model=QuestionPublic)
def get_question(question_id: UUID, db: Session = Depends(get_db)):
    return question_service.get_question(db, question_id)

