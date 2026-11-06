# Legal expert evaluation platform

This hackathon MVP collects legal questions, AI answers, and human expert judgments, then exports structured JSONL. It does not train models or send records to Mercor. Expert review is the source of verification.

## Scope and architecture

**Do not modify, delete, rename, format, or generate files inside frontend/. Do not change frontend dependencies, package.json, configuration, or assets. Do not run repository-wide formatters that change frontend files. Frontend inspection is read-only. All implementation changes must stay within backend/ and root AGENTS.md; document needs elsewhere. Preserve existing user changes.**

Repository map:
- frontend/: owned by another teammate; read-only.
- backend/app/main.py: FastAPI app, configurable CORS, route registration.
- backend/app/api/routes/: HTTP contracts; schemas/: Pydantic validation and public serialization.
- backend/app/services/: question, generation, evaluation, export business logic.
- backend/app/db/: SQLAlchemy models, engine, injected synchronous sessions.
- backend/app/ai/: provider protocol, deterministic mock, OpenAI adapter, prompt version.
- backend/app/core/config.py: cached environment settings.
- backend/app/seed.py: five idempotent fictional examples.
- backend/alembic/: versioned schema and SQLite immutability triggers.
- backend/tests/: migrated temporary SQLite API tests.

Stack: Python 3.11+, FastAPI, Pydantic v2/pydantic-settings, SQLAlchemy 2.x, SQLite, Alembic, OpenAI SDK, Uvicorn, pytest, HTTPX. No startup create_all, queues, Docker, or auth.

## Contracts

- GET /health: healthy status.
- POST/GET /api/v1/questions: create/list; list filters domain and difficulty.
- GET /api/v1/questions/{question_id}: public details.
- POST /api/v1/questions/{question_id}/generate: persist a new generation (201, inspect status).
- GET /api/v1/generations/{generation_id}: answer and status.
- POST/GET /api/v1/evaluations: submit/list.
- GET /api/v1/evaluations/{evaluation_id}: individual review.
- GET /api/v1/exports/evaluations: downloadable JSONL, one review per line.

Lists are arrays; offset >= 0, limit 1–200 (default 50). Validation 422, missing records 404, unfinished-generation review 409. FastAPI errors use detail.

Entities use UUIDs, UTC timestamps, explicit foreign keys:
- Question: title, question_text, domain, jurisdiction, relevant_law_date, difficulty (easy/medium/hard), private reference_answer/reference_sources, created_at/updated_at.
- Generation: question_id, model_name, ai_answer, status (pending/completed/failed), sanitized error_message, prompt_version, created_at.
- Evaluation: question_id, generation_id, optional reviewer_id, verdict, error_categories, expert_explanation, optional corrected_answer/supporting_sources/confidence (1–5), created_at.

Citation fields: title, optional citation/url/jurisdiction. Export shape: schema_version, public question, generation, evaluation.

## Invariants and security

- Never pass reference answers or sources to a provider. Build provider inputs with an explicit public field allowlist; public responses and exports omit references.
- Never infer correctness from reference text matching. Correct verdict yields expert_approved, never proven correct; uncertain permits abstention (expert_abstained).
- Incorrect/partially_correct require nonblank explanation and corrected answer.
- Reviews must match the question and completed generation. Completed/failed generations cannot be edited; create another generation instead.
- Error taxonomy: hallucinated_authority, outdated_law, wrong_jurisdiction, incorrect_interpretation, missing_authority, incomplete_answer, incorrect_conclusion, unsupported_claim, other.
- Never fabricate supporting authorities or claim simulated answers are real model failures.
- AI_PROVIDER defaults to mock. Missing OpenAI key falls back to mock. Unit tests never call OpenAI.
- Never commit keys, .env, local databases, confidential legal material, or provider exception text. No authentication exists; reviewer identity is unverified. Use fictional data locally; production access controls are outside this MVP.

## Commands and conventions

From backend/ (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env # initial setup only; preserve existing configuration
python -m alembic upgrade head
python -m app.seed
python -m uvicorn app.main:app --reload
python -m pytest -q
python -m alembic check
```
Swagger: http://localhost:8000/docs. Use source .venv/bin/activate on POSIX. .env and relative database paths resolve from backend/.

Use type hints, small functions, explicit response schemas, injected sessions, service-layer business logic, and migrations for schema changes. Keep providers separate from routes and database objects. Do not add infrastructure without need.

Before changes:
1. Read this file and backend/README.md; inspect git status and relevant code.
2. Confirm scope and preserve user edits; never write frontend/.
3. Identify public contract, reference privacy, review, and immutability implications.
4. Make focused changes and migrations where needed; add meaningful tests.

Done means working implementation, relevant tests passing without external AI, migrations applied and checked, app import/OpenAPI verified, documentation matching actual behavior, no frontend changes, and a concise report of checks and genuine limitations.

