from datetime import date, datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text, Uuid, event, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
def utcnow() -> datetime:
    return datetime.now(timezone.utc)
class Question(Base):
    __tablename__ = "questions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(250))
    question_text: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(100), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(250))
    relevant_law_date: Mapped[date] = mapped_column(Date)
    scenario_facts: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(10), index=True)
    reference_answer: Mapped[str | None] = mapped_column(Text)
    reference_sources: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    generations: Mapped[list["Generation"]] = relationship(back_populates="question")
class Generation(Base):
    __tablename__ = "generations"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(200))
    ai_answer: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str | None] = mapped_column(String(30))
    structured_answer: Mapped[dict | None] = mapped_column(JSON)
    generation_metadata: Mapped[dict | None] = mapped_column(JSON)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_category: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    question: Mapped[Question] = relationship(back_populates="generations")
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="generation")
class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"), index=True)
    generation_id: Mapped[UUID] = mapped_column(ForeignKey("generations.id"), index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(200))
    verdict: Mapped[str] = mapped_column(String(30))
    error_categories: Mapped[list] = mapped_column(JSON)
    expert_explanation: Mapped[str] = mapped_column(Text)
    corrected_answer: Mapped[str | None] = mapped_column(Text)
    correction_unavailable_reason: Mapped[str | None] = mapped_column(Text)
    independent_expert_answer: Mapped[str | None] = mapped_column(Text)
    independent_answer_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supporting_sources: Mapped[list | None] = mapped_column(JSON)
    confidence: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    generation: Mapped[Generation] = relationship(back_populates="evaluations")
@event.listens_for(Generation, "before_update")
def protect_generation(mapper, connection, target):
    state = inspect(target)
    history = state.attrs.status.history.deleted
    previous = history[0] if history else target.status
    if previous in ("completed", "failed") and any(state.attrs[key].history.has_changes() for key in mapper.column_attrs.keys()):
        raise ValueError("Terminal generations are immutable")

