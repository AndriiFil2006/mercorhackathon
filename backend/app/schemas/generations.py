from datetime import datetime
from typing import Literal
from uuid import UUID
from app.schemas.questions import ORMResponse
class GenerationPublic(ORMResponse):
    id: UUID
    question_id: UUID
    model_name: str
    ai_answer: str
    status: Literal["pending", "completed", "failed"]
    error_message: str | None
    prompt_version: str
    created_at: datetime

