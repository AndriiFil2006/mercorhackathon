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
- backend/app/ai/: narrow input/result schemas, stable system prompt, structured Gemini adapter (official google-genai SDK), deterministic mock, optional OpenAI adapter, sanitized errors.
- backend/app/core/config.py: cached environment settings.
- backend/app/seed.py: five idempotent fictional examples.
- backend/app/demo.py: five narrow unverified fictional benchmarks; explicit manual Gemini smoke command.
- backend/alembic/: versioned schema and SQLite immutability triggers.
- backend/tests/: migrated temporary SQLite API tests.

Stack: Python 3.11+, FastAPI, Pydantic v2/pydantic-settings, SQLAlchemy 2.x, SQLite, Alembic, official google-genai and optional OpenAI SDKs, Uvicorn, pytest, HTTPX. No startup create_all, queues, Docker, or auth.

## Contracts

- GET /health: healthy status.
- POST/GET /api/v1/questions: create/list; list filters domain and difficulty.
- GET /api/v1/questions/{question_id}: public details.
- POST /api/v1/questions/{question_id}/generate: synchronous, fresh generation per call; 201 completed, 429/502/503/504 failed with generation body and sanitized error_category. GET never generates.
- GET /api/v1/generations/{generation_id}: answer and status.
- POST/GET /api/v1/evaluations: submit/list.
- GET /api/v1/evaluations/{evaluation_id}: individual review.
- GET /api/v1/exports/evaluations: downloadable JSONL, one review per line.

Lists are arrays; offset >= 0, limit 1–200 (default 50). Validation 422, missing records 404, unfinished-generation review 409. FastAPI errors use detail.

Entities use UUIDs, UTC timestamps, explicit foreign keys:
- Question: title, question_text, domain, jurisdiction, relevant_law_date, optional public scenario_facts, difficulty (easy/medium/hard), private reference_answer/reference_sources, created_at/updated_at.
- Generation: question_id, provider, requested model_name, ai_answer, structured_answer, generation_metadata (reported model_used/token usage/attempts/duration/simulated), status (pending/completed/failed), sanitized error_message/error_category, prompt_version, created_at/completed_at. Added fields are nullable for historical records; never guess historical metadata.
- Evaluation: question_id, generation_id, optional reviewer_id, verdict, error_categories, expert_explanation, optional corrected_answer/correction_unavailable_reason/supporting_sources/confidence (1–5), independent_expert_answer/independent_answer_received_at, created_at.

Reviewer citation fields: title, optional citation/url/jurisdiction. Model citations: authority_name/citation/relevance, always unverified. Structured answers: short_answer/legal_rules/analysis/exceptions_or_limitations/conclusion/citations/uncertainties. Export schema_version=1.1 retains nested public question/generation/evaluation.

## Invariants and security

- Never pass references, evaluations, title, or difficulty to a provider. LegalGenerationInput contains only public question text/domain/jurisdiction/law date/scenario facts plus correlation ID (not prompted). Build the input explicitly; never serialize a DB model. Public responses/exports omit references.
- Never infer correctness from reference text matching. Correct verdict yields expert_approved, never proven correct; uncertain permits abstention (expert_abstained).
- Incorrect/partially_correct require nonblank explanation and corrected answer or correction_unavailable_reason.
- Independent answers are optional and timestamped at evaluation receipt, not drafting time. No enforced pre-reveal workflow exists; never claim blinding. Reviewer identity is unverified (reviewer_identity_verified=false); mark demo feedback unverified. Review status is submitted, not legally proven.
- Reviews must match the question and completed generation. Completed/failed generations cannot be edited; create another generation instead.
- Error taxonomy: hallucinated_authority, outdated_law, wrong_jurisdiction, incorrect_interpretation, missing_authority, incomplete_answer, incorrect_conclusion, unsupported_claim, other.
- Never fabricate supporting authorities or claim simulated answers are real model failures.
- AI_PROVIDER defaults to mock; gemini is the primary real provider with default GEMINI_MODEL=gemini-2.5-flash. Gemini requires GEMINI_API_KEY and never falls back to mock. Optional OpenAI retains historical no-key mock fallback.
- The historical 2.5 code default is now rejected as retired by Google. The environment example explicitly selects gemini-3.1-flash-lite (live smoke verified). Preserve explicit model selection and record its exact ID; never silently substitute. Use response_json_schema rather than the legacy response_schema converter, and omit deprecated sampling parameters for Gemini 3 models.
- AI_PROMPT_VERSION defaults legal-v1. Keep the supplied system prompt stable. Separate system instructions from untrusted public scenario JSON. Never execute scenario content. Model citations are not independently verified.
- Gemini timeout/output/retries: GEMINI_TIMEOUT_SECONDS=45, GEMINI_MAX_OUTPUT_TOKENS=2048, GEMINI_MAX_RETRIES=2. One normal call; transient-only bounded retries, SDK retries disabled, Retry-After honored (fail rather than wait over 30s). No repair/judge/summarization calls. Log IDs/model/duration/categories, never secrets/scenario/raw exceptions.
- Tests use mocked SDK or offline transport and temporary migrated DBs, never live Gemini/OpenAI. Live smoke is manual only.
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
python -m app.demo seed
python -m uvicorn app.main:app --reload
python -m pytest -q
python -m alembic check
```
Swagger: http://localhost:8000/docs. Use source .venv/bin/activate on POSIX. .env and relative database paths resolve from backend/.
Configure Gemini in backend/.env, restart the server, then optionally run `python -m app.demo smoke QUESTION_UUID` for one explicit live generation (may consume quota). No live request runs automatically. See backend/README.md for full workflow and sanitized error contracts.

Use type hints, small functions, explicit response schemas, injected sessions, service-layer business logic, and migrations for schema changes. Keep providers separate from routes and database objects. Do not add infrastructure without need.

Before changes:
1. Read this file and backend/README.md; inspect git status and relevant code.
2. Confirm scope and preserve user edits; never write frontend/.
3. Identify public contract, reference privacy, review, and immutability implications.
4. Make focused changes and migrations where needed; add meaningful tests.

Done means working implementation, relevant tests passing without external AI, migrations applied and checked, app import/OpenAPI verified, documentation matching actual behavior, no frontend changes, and a concise report of checks and genuine limitations.

