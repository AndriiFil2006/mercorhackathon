import json
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.db.models import Evaluation, Generation
from app.schemas.questions import QuestionPublic
from app.schemas.generations import GenerationPublic
from app.schemas.evaluations import EvaluationPublic
def export_evaluations(db: Session):
    statement = select(Evaluation).options(
        joinedload(Evaluation.generation).joinedload(Generation.question)
    ).order_by(Evaluation.created_at, Evaluation.id).execution_options(yield_per=100)
    for evaluation in db.scalars(statement):
        generation = evaluation.generation
        yield json.dumps({
            "schema_version": "1.1",
            "question": QuestionPublic.model_validate(generation.question).model_dump(mode="json"),
            "generation": GenerationPublic.model_validate(generation).model_dump(mode="json"),
            "evaluation": EvaluationPublic.model_validate(evaluation).model_dump(mode="json"),
        }, ensure_ascii=False) + "\n"

