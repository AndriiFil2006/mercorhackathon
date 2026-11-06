"""Idempotent fictional demo questions; run after alembic upgrade head."""
from datetime import date
from uuid import NAMESPACE_URL, uuid5
from app.db.models import Question
from app.db.session import SessionLocal

EXAMPLES = [
    ("Contract law", "New York, United States", "Fictional Alder Studio orders custom desks from fictional Birch Works. Delivery is late and the agreement contains a limitation of remedies. What facts affect the buyer's remedies?"),
    ("Employment law", "California, United States", "Fictional employee Mira at fictional Copper Labs is classified as a contractor but works assigned shifts. What facts matter for classification?"),
    ("Landlord-tenant law", "Massachusetts, United States", "Fictional tenant Owen rents from fictional Elm Homes. A heating failure remains unresolved after written notice. What options and procedural risks should be reviewed?"),
    ("Consumer protection", "Washington, United States", "Fictional shopper Nila buys a subscription from fictional Fern Media advertised as cancel-anytime, but cancellation is refused. What issues should counsel investigate?"),
    ("Intellectual property", "United States federal law", "Fictional artist Tavi discovers fictional Grove Goods copied an original illustration onto packaging. What copyright issues and defenses should counsel assess?"),
]
def seed() -> int:
    added = 0
    with SessionLocal() as db:
        for domain, jurisdiction, text in EXAMPLES:
            question_id = uuid5(NAMESPACE_URL, f"legal-eval-demo-v1:{domain}")
            if db.get(Question, question_id) is not None:
                continue
            db.add(Question(id=question_id, title=f"[FICTIONAL DEMO] {domain}", question_text=text,
                            domain=domain, jurisdiction=jurisdiction, relevant_law_date=date(2025, 1, 1),
                            difficulty="medium"))
            added += 1
        db.commit()
    return added
if __name__ == "__main__":
    print(f"Added {seed()} fictional demo questions.")

