from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.evaluations import EvaluationCreate, EvaluationPublic
from app.services import evaluation_service
router = APIRouter(prefix="/evaluations", tags=["evaluations"])
@router.post("", response_model=EvaluationPublic, status_code=201)
def create_evaluation(data: EvaluationCreate, db: Session = Depends(get_db)):
    return evaluation_service.create_evaluation(db, data)
@router.get("", response_model=list[EvaluationPublic])
def list_evaluations(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                     db: Session = Depends(get_db)):
    return evaluation_service.list_evaluations(db, offset, limit)
@router.get("/{evaluation_id}", response_model=EvaluationPublic)
def get_evaluation(evaluation_id: UUID, db: Session = Depends(get_db)):
    return evaluation_service.get_evaluation(db, evaluation_id)

