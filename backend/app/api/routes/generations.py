from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.generations import GenerationPublic
from app.services import generation_service
router = APIRouter(tags=["generations"])
@router.post("/questions/{question_id}/generate", response_model=GenerationPublic, status_code=201,
             responses={code: {"model": GenerationPublic, "description": "Persisted failed generation"}
                        for code in (429, 502, 503, 504)})
def generate_answer(question_id: UUID, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    generation = generation_service.generate_answer(db, question_id, settings)
    response.status_code = generation_service.generation_http_status(generation)
    return generation
@router.get("/generations/{generation_id}", response_model=GenerationPublic)
def get_generation(generation_id: UUID, db: Session = Depends(get_db)):
    return generation_service.get_generation(db, generation_id)

