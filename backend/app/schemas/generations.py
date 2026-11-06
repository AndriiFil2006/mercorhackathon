from datetime import datetime
from typing import Literal
from uuid import UUID
from app.schemas.questions import ORMResponse
from app.ai.schemas import StructuredLegalAnswer
class GenerationPublic(ORMResponse):
    id: UUID
    question_id: UUID
    model_name: str
    ai_answer: str
    status: Literal["pending", "completed", "failed"]
    error_message: str | None
    prompt_version: str
    created_at: datetime
    provider: str | None = None
    structured_answer: StructuredLegalAnswer | None = None
    generation_metadata: dict | None = None
    completed_at: datetime | None = None
    error_category: str | None = None

