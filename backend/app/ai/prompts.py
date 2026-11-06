from app.schemas.questions import PublicQuestionInput
PROMPT_VERSION = "legal-review-v1"
def build_prompt(question: PublicQuestionInput) -> str:
    return (
        "Answer this fictional legal scenario. State uncertainty and jurisdiction limits. "
        "Do not invent authorities. Human expert review is required.\n"
        f"Jurisdiction: {question.jurisdiction}\nLaw date: {question.relevant_law_date}\n"
        f"Domain: {question.domain}\nQuestion: {question.question_text}"
    )

