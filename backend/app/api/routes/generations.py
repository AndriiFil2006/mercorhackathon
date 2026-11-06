from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.generations import GenerationPublic
from app.services import generation_service
router = APIRouter(tags=["generations"])
@router.post("/questions/{question_id}/generate", response_model=GenerationPublic, status_code=201)
def generate_answer(question_id: UUID, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return generation_service.generate_answer(db, question_id, settings)
@router.get("/generations/{generation_id}", response_model=GenerationPublic)
def get_generation(generation_id: UUID, db: Session = Depends(get_db)):
    return generation_service.get_generation(db, generation_id)

