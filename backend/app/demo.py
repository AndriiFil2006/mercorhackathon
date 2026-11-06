"""Explicit demo commands; never generates on import or application startup."""
import argparse
from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from app.db.models import Question
from app.db.session import SessionLocal

# Questions only: no asserted expected answers or fabricated authorities.
DEMO_QUESTIONS = [
    ("Contract law", "New York, United States", "Oral sale and enforceability", "hard",
     "Can the seller enforce this agreement on the stated facts? Distinguish any applicable writing requirement and exceptions.",
     "Fictional Alder Desks orally agrees to sell 20 standard desks to fictional Birch Office for $4,000. Neither party signs a writing. No payment, delivery, admission in court, or specially manufactured goods are involved. Assume both parties are merchants."),
    ("Employment law", "California, United States", "Final wage timing on discharge", "medium",
     "When are the earned wages due on discharge? Distinguish discharge from resignation and identify any material qualifications.",
     "Fictional Mira is a non-union office employee at fictional Copper Studio. The employer discharges Mira at noon on Monday. Earned wages are undisputed. Assume no industry-specific exception applies."),
    ("Landlord-tenant law", "Massachusetts, United States", "Security deposit deductions", "hard",
     "May a landlord deduct the stated cost from a residential security deposit? Identify the governing distinction and any documentation requirements.",
     "Fictional Elm Homes rents an apartment to fictional Owen. At the end of the tenancy, the landlord wants to deduct repainting costs solely for ordinary wear from normal use. There is no unpaid rent or tenant-caused damage beyond ordinary wear."),
    ("Consumer protection", "United States federal law", "Rescission of home purchase financing", "hard",
     "Does the federal Truth in Lending Act's three-business-day rescission right apply to the described purchase financing? Distinguish other secured credit transactions.",
     "Fictional Nila borrows from fictional Fern Bank solely to finance the initial purchase of Nila's principal dwelling. The loan is secured by that dwelling. It is not a refinance or home equity loan."),
    ("Intellectual property", "United States federal law", "Registration before an infringement suit", "medium",
     "Can the creator file a copyright infringement action now solely on the basis of the pending application? Identify relevant exceptions and assumptions.",
     "Fictional Tavi created a United States work and submitted a copyright registration application yesterday. The Copyright Office has neither registered nor refused it. Fictional Grove Goods allegedly copied it. No preregistration or live-broadcast exception is claimed."),
]


def seed_demo() -> list[UUID]:
    ids = []
    with SessionLocal() as db:
        for domain, jurisdiction, title, difficulty, text, facts in DEMO_QUESTIONS:
            question_id = uuid5(NAMESPACE_URL, f"legal-eval-narrow-demo-v1:{title}")
            ids.append(question_id)
            if db.get(Question, question_id) is None:
                db.add(Question(
                    id=question_id, title=f"[FICTIONAL BENCHMARK — UNVERIFIED] {title}",
                    question_text=text, scenario_facts=facts, domain=domain,
                    jurisdiction=jurisdiction, relevant_law_date=date(2025, 1, 1), difficulty=difficulty,
                ))
        db.commit()
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Add five narrow fictional questions; no AI requests")
    smoke = sub.add_parser("smoke", help="Manually POST one generation; may consume Gemini quota")
    smoke.add_argument("question_id", type=UUID)
    smoke.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    if args.command == "seed":
        for question_id in seed_demo():
            print(question_id)
        return
    with httpx.Client(timeout=360) as client:
        response = client.post(f"{args.base_url.rstrip('/')}/api/v1/questions/{args.question_id}/generate")
    try:
        result = response.json()
    except ValueError:
        raise SystemExit(f"Backend returned HTTP {response.status_code}; inspect backend availability.") from None
    if response.is_error:
        # Print only known sanitized generation fields, never raw arbitrary HTTP content.
        raise SystemExit(f"Generation failed: HTTP {response.status_code}, category={result.get('error_category', 'unknown')}, id={result.get('id', 'unknown')}")
    print(f"generation_id={result['id']} provider={result['provider']} model={result['model_name']} status={result['status']}")
    if result["provider"] != "gemini":
        raise SystemExit("This was not a Gemini smoke test. Configure the server with AI_PROVIDER=gemini and restart it.")


if __name__ == "__main__":
    main()
