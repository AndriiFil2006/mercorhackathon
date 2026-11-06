"""Print configuration presence, never values of API keys. --providers is explicit network."""

import argparse
import subprocess
from pathlib import Path
import httpx
from app.core.config import get_settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--providers",
        action="store_true",
        help="Explicit Gemini/Groq model-list API requests; no model generation",
    )
    args = parser.parse_args()
    settings = get_settings()
    root = Path(__file__).resolve().parents[2]
    print("Backend environment file exists:", (root / "backend/.env").exists())
    print("AI provider:", settings.ai_provider, "Gemini model:", settings.gemini_model)
    print("Review mode:", settings.review_mode)
    for label, value in [
        ("Gemini", settings.gemini_api_key),
        ("Groq", settings.groq_api_key),
        ("Tavily", settings.tavily_api_key),
    ]:
        print(label, "key present:", bool(value.strip()))
    for filename in ("backend/.env", "frontend/.env.local"):
        tracked = subprocess.run(
            ["git", "ls-files", "--", filename],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        ignored = (
            subprocess.run(
                ["git", "check-ignore", "--", filename],
                cwd=root,
                capture_output=True,
                text=True,
            ).returncode
            == 0
        )
        print(filename, "tracked:", bool(tracked), "ignored:", ignored)
        if tracked or not ignored:
            raise SystemExit("Fix private-file Git protection before staging anything.")
    models = [
        settings.review_model_authority,
        settings.review_model_jurisdiction,
        settings.review_model_reasoning,
    ]
    print("Distinct reviewer model IDs:", len(set(models)) == 3)
    if args.providers:
        with httpx.Client(timeout=30) as client:
            if settings.gemini_api_key:
                response = client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    headers={"x-goog-api-key": settings.gemini_api_key},
                )
                print("Gemini model-list status:", response.status_code)
                if response.is_success:
                    available = {
                        m["name"].removeprefix("models/")
                        for m in response.json().get("models", [])
                    }
                    print(
                        "Configured Gemini model listed:",
                        settings.gemini_model.removeprefix("models/") in available,
                    )
            if settings.groq_api_key:
                response = client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                )
                print("Groq model-list status:", response.status_code)
                if response.is_success:
                    available = {m["id"] for m in response.json().get("data", [])}
                    for model in models:
                        print(model, "listed:", model in available)
                    print("Available IDs:", ", ".join(sorted(available)))
        print(
            "Model listing is not a guarantee of account-specific free generation quota. Check each console; do not enable paid billing."
        )
    print("No model generation or search requests were made by this setup check.")


if __name__ == "__main__":
    main()
