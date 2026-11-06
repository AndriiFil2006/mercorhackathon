"""Explicit end-to-end HTTP smoke; uses fictional data, never prints bearer tokens."""

import argparse
import sys
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--consent-external", action="store_true")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=600, trust_env=False) as client:
        config = client.get("/api/legal/config")
        config.raise_for_status()
        config = config.json()
        if args.live:
            if not args.consent_external:
                raise SystemExit(
                    "Live calls require --consent-external. They consume your free quotas."
                )
            if config["answerProvider"] != "gemini" or config["reviewMode"] != "live":
                raise SystemExit(
                    "Set AI_PROVIDER=gemini and REVIEW_MODE=live, then restart the backend."
                )
        elif config["answerProvider"] != "mock" or config["reviewMode"] != "mock":
            raise SystemExit(
                "Offline smoke refuses to call live services. Set both modes to mock, or explicitly use --live --consent-external."
            )

        def post(path, data):
            response = client.post("/api/legal/" + path, json=data)
            if not response.is_success:
                try:
                    detail = response.json().get("detail", "No detail")
                except ValueError:
                    detail = "Non-JSON response"
                raise SystemExit(f"{path}: HTTP {response.status_code}: {detail}")
            return response.json()

        question = "Fictional California residential tenant: the landlord kept the deposit after move-out without an itemized statement. What issues and exceptions should be assessed?"
        common = {
            "question": question,
            "jurisdiction": "United States, California",
            "lawDate": "2026-11-06",
            "externalConsent": True,
        }
        answer = post("answer", {**common, "messages": []})
        print(
            "Main answer:",
            answer["mode"],
            answer["model"],
            "generation:",
            answer["generationId"],
        )
        reports = []
        for reviewer in ["authority", "jurisdiction", "reasoning"]:
            report = post(
                "review",
                {
                    **common,
                    "reviewer": reviewer,
                    "answer": answer["answer"],
                    "generationId": answer["generationId"],
                },
            )
            reports.append(report)
            print(
                "Reviewer:",
                reviewer,
                "model:",
                report["model"],
                "status:",
                report["status"],
                "score:",
                report["score"],
                "sources:",
                len(report["sources"]),
            )
        explanation = post(
            "review-chat",
            {
                **common,
                "answer": answer["answer"],
                "reviews": reports,
                "history": [],
                "prompt": "Explain the criterion deductions, agreements and unresolved research.",
            },
        )
        print("Scorer follow-up returned:", bool(explanation["answer"]))
        handoff = post(
            "handoff",
            {
                "consentProcessing": True,
                "consentShareContext": True,
                "context": {
                    "id": "smoke-inquiry",
                    "title": "Fictional smoke inquiry",
                    "jurisdiction": common["jurisdiction"],
                    "lawDate": common["lawDate"],
                    "messages": [
                        {"role": "user", "text": question},
                        {"role": "assistant", "text": answer["answer"]},
                    ],
                    "evaluations": [
                        {
                            "question": question,
                            "answer": answer["answer"],
                            "reviews": reports,
                            "scorerMessages": [
                                {"role": "assistant", "text": explanation["answer"]}
                            ],
                        }
                    ],
                    "selectedEvaluationId": "smoke-answer",
                },
            },
        )
        token = handoff["handoffToken"]
        try:
            lawyer = post(
                "lawyer-chat",
                {
                    "handoffToken": token,
                    "message": "Explain the unresolved issues using the complete shared snapshot.",
                },
            )
            print(
                "AI legal assistant replied:",
                bool(lawyer["answer"]),
                "real lawyer:",
                lawyer["realLawyer"],
            )
        finally:
            result = client.post(
                "/api/legal/handoff/revoke", json={"handoffToken": token}
            )
            result.raise_for_status()
        blocked = client.post(
            "/api/legal/lawyer-chat",
            json={"handoffToken": token, "message": "Must be blocked"},
        )
        assert blocked.status_code == 410
        print(
            "Consent revocation blocked subsequent processing. End-to-end smoke complete."
        )


if __name__ == "__main__":
    main()
