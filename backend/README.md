# Legal AI generation and expert evaluation

This FastAPI backend implements Mercor's specialized-domain verification workflow: submit a legal question, generate an independent answer, have a human review that exact answer, and export the review as JSONL. Gemini is the primary real-model integration. Mock mode is offline and deterministic. Generation success is never legal verification. No model training, automatic LLM judging, or Mercor transmission occurs.

## Install and run

Python 3.11+; verified here on Python 3.14. Run in PowerShell from the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env # first setup only; do not overwrite an existing .env
python -m alembic upgrade head
python -m app.seed
python -m app.demo seed
python -m uvicorn app.main:app --reload
```

On macOS/Linux use `source .venv/bin/activate` and `cp .env.example .env`. All subsequent commands run from backend/. Relative DATABASE_URL and .env paths resolve there. Migrations preserve existing records; no create_all runs on startup. Newly added metadata is null for historical generations rather than guessed or rewritten.

Swagger: http://localhost:8000/docs
OpenAPI: http://localhost:8000/openapi.json

## Gemini configuration

Edit local backend/.env, then restart the server:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=YOUR_GOOGLE_AI_STUDIO_KEY
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_TIMEOUT_SECONDS=45
GEMINI_MAX_RETRIES=2
GEMINI_MAX_OUTPUT_TOKENS=2048
AI_PROMPT_VERSION=legal-v1
DATABASE_URL=sqlite:///./legal_eval.db
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

The official maintained `google-genai` SDK calls `client.models.generate_content` with `response_json_schema=StructuredLegalAnswer.model_json_schema()` and a separate system instruction. Pydantic validates the result locally. The legacy `response_schema` converter is deliberately avoided: it can emit snake_case schema keywords rejected by Gemini with HTTP 400. See [SDK documentation](https://googleapis.github.io/python-genai/) and [structured output documentation](https://ai.google.dev/gemini-api/docs/structured-output).

AI_PROVIDER=mock is the safe default in settings and .env.example: no API key or network is needed. Supported providers are mock, gemini, and optional openai. The existing OpenAI configuration (OPENAI_API_KEY and OPENAI_MODEL) remains supported, including its historical no-key mock fallback. Gemini requires GEMINI_API_KEY and **never** falls back to mock on failure. Model IDs are not automatically substituted; unavailable models produce an actionable failed generation.

Normal generation makes one request. Only transient timeouts, connection failures, 408/429, and selected 5xx errors retry, up to GEMINI_MAX_RETRIES (0–5). SDK-level retries are disabled to avoid multiplying attempts. Backoff is 1/2/4/8 seconds, capped at 8; Retry-After or Google RetryInfo takes precedence. A requested delay over 30 seconds ends the attempt rather than retrying too early. Credentials and invalid requests are not retried. Each timeout is per attempt, so total synchronous latency may exceed GEMINI_TIMEOUT_SECONDS.

The historical code default remains gemini-2.5-flash for compatibility, but Google now rejects generation requests for that retired model. Explicitly configure a supported model; the example uses gemini-3.1-flash-lite, which completed a live structured-generation smoke test. Gemini 3.8 Flash was also listed but timed out at both 45 and 90 seconds during local testing. A model-list entry alone does not guarantee a model still accepts generation requests. See [Google's model documentation](https://ai.google.dev/gemini-api/docs/models).

Gemini 3 models use LOW thinking level and omit deprecated sampling parameters; older models use temperature 0.2, with thinking_budget=0 for 2.5 Flash. No hidden chain of thought is collected. Remote model output is not deterministic. Reported model version, response ID, token usage when available, attempts, and duration are stored as generation_metadata. If a supported model exceeds the 45-second default, set GEMINI_TIMEOUT_SECONDS=90 and restart the backend.

Do not enable billing automatically or bulk-generate on startup. Configure model availability and quota in your own Google project.

## Public API workflow

These curl commands use POSIX quoting; on Windows use curl.exe with JSON files or PowerShell Invoke-RestMethod. Replace uppercase UUID placeholders with IDs from previous responses.

```sh
curl http://localhost:8000/health

curl -X POST http://localhost:8000/api/v1/questions \
  -H 'Content-Type: application/json' -d '{
    "title":"Fictional final-wage question",
    "question_text":"When are undisputed earned wages due on discharge, assuming no industry-specific exception?",
    "domain":"Employment law",
    "jurisdiction":"California, United States",
    "relevant_law_date":"2025-01-01",
    "scenario_facts":"Fictional Mira, a non-union office employee at fictional Copper Studio, is discharged at noon on Monday.",
    "difficulty":"medium"
  }'

curl 'http://localhost:8000/api/v1/questions?difficulty=medium&offset=0&limit=50'
curl http://localhost:8000/api/v1/questions/QUESTION_UUID

curl -X POST http://localhost:8000/api/v1/questions/QUESTION_UUID/generate
curl http://localhost:8000/api/v1/generations/GENERATION_UUID

curl -X POST http://localhost:8000/api/v1/evaluations \
  -H 'Content-Type: application/json' -d '{
    "question_id":"QUESTION_UUID",
    "generation_id":"GENERATION_UUID",
    "reviewer_id":"unverified-demo-reviewer",
    "verdict":"uncertain",
    "expert_explanation":"Demo feedback only: primary sources and reviewer qualifications have not been verified.",
    "independent_expert_answer":"Optional previously drafted answer; this field does not establish blind review.",
    "error_categories":[],
    "supporting_sources":[],
    "confidence":2
  }'

curl http://localhost:8000/api/v1/evaluations
curl http://localhost:8000/api/v1/evaluations/EVALUATION_UUID
curl -o evaluations.jsonl http://localhost:8000/api/v1/exports/evaluations
```

POST generation is synchronous. It first commits a pending row, calls only the configured provider, validates the result, formats the readable answer, then stores completion. Each POST creates a new UUID; GETs never call a model.

Existing ai_answer remains the exact readable text saved and shown to reviewers. Additive response fields include provider, structured_answer, generation_metadata, completed_at, and error_category. Structured answers contain short_answer, legal_rules, analysis, exceptions_or_limitations, conclusion, citations, and uncertainties. Lists are always arrays; unavailable authorities are empty arrays. Model citations have authority_name, citation, and relevance and are explicitly **unverified**.

### Status and errors

- Creates return 201. Lists return arrays, offset >= 0, limit 1–200 (default 50); question lists filter domain and difficulty.
- Missing resources return 404; invalid inputs or mismatched review IDs 422; review of a non-completed generation 409.
- Failed generation POSTs return the persisted generation body, including its id and status=failed: 429 quota/rate limits, 504 timeouts, 503 configuration/authentication/model unavailable/provider unavailable, 502 blocked/empty/malformed/invalid output and unexpected provider errors.
- This replaces the original 201-on-provider-failure behavior while retaining the generation response fields. Frontend clients should inspect both HTTP status and body, then use GET to retrieve the saved status.
- Error strings are sanitized. Raw provider messages, credentials, and question contents are not logged. Persistence failures return sanitized 503 detail; if a pending ID exists it is included so clients can inspect it before retrying.
- Malformed output is rejected, never repaired by a second model call. A process crash can leave a pending row. Create a fresh generation when appropriate.

## Blind generation and expert feedback

Providers receive only question text, domain, jurisdiction, relevant law date, and public scenario facts. The input carries a question ID for correlation, which is not sent in the prompt. Reference answers/sources, title, difficulty, expected labels, grading criteria, and previous evaluations never cross that boundary. Publicly supplied legal materials can be included in scenario_facts. The system prompt treats scenario text as untrusted data and offers no tools or secret access; prompt instructions cannot guarantee that an LLM always resists malicious instructions.

Question creation can store reference_answer and reference_sources for benchmarks. They are excluded from all public responses, prompts, and exports. No admin export exists.

Verdicts: correct, partially_correct, incorrect, uncertain. Incorrect/partially_correct require a nonblank expert_explanation plus either corrected_answer or correction_unavailable_reason. Uncertain supports abstention without a correction. The fixed error taxonomy remains unchanged; consult Swagger.

Review citation objects use title (required), optional citation/url/jurisdiction. Authorities are supplied by the reviewer; the backend does not verify or fetch them. Expert feedback never changes the saved AI answer. Completed/failed generations are immutable via ORM and SQLite update/delete triggers.

Optional independent_expert_answer can accompany an evaluation. independent_answer_received_at is assigned by the server at evaluation receipt, **not** at purported drafting time. There is no enforced pre-reveal workflow, so no blind-review claim is made. Clients cannot supply this timestamp.

All reviews have review_status=submitted and reviewer_identity_verified=false. A supplied reviewer_id is not proof of legal qualifications. verification_status=expert_approved records a claimed human judgment for correct verdicts; it is not mathematical proof or confirmation that a licensed lawyer reviewed the answer. Uncertain produces expert_abstained. Label demo reviews as unverified feedback.

## JSONL export

Each line retains the existing nested shape with schema_version=1.1:
- question: public details, including id/domain/jurisdiction/law date/scenario facts.
- generation: exact ai_answer, structured_answer, provider, requested model_name, prompt_version, timestamps, metadata (including model_used if reported).
- evaluation: review ID, generation/question IDs, verdict, categories, explanation, correction or correction-unavailable reason, independent answer/receipt time, supporting sources, confidence, review status and unverified reviewer identity.

Only submitted reviews are exported, one per line; multiple reviews yield separate records. Unreviewed generations are absent. Simulated records retain provider=mock and generation_metadata.simulated=true. Historical rows may have null provider/structured data. Hidden references are always excluded.

## Demo and optional live smoke test

`python -m app.seed` retains the five original broad fictional examples. `python -m app.demo seed` adds five narrow, clearly unverified fictional benchmark questions covering contract formation, final wages, security deposits, consumer credit, and copyright registration. Both commands are idempotent and never overwrite existing questions. Neither invokes a model or creates expert feedback. No reference answers or authoritative expected verdicts are asserted.

For a real benchmark:
1. Have a qualified expert independently establish the expected answer against primary authorities at the stated law date.
2. Keep that analysis outside the generating model input. Have the reviewer draft an independent answer before revealing the AI output if desired; this MVP cannot enforce blinding.
3. Explicitly POST a fresh Gemini generation. Preserve its unmodified saved answer.
4. Have the expert submit a verdict with reasoning and sources. Do not force a desired error rate.
5. Export the record. If no qualified expert reviewed it, label the feedback demo/unverified.

Optional manual smoke test, with the server configured for Gemini and a valid key:
```sh
python -m app.demo seed
python -m app.demo smoke QUESTION_UUID
```
Use one printed UUID. This makes one explicit generation POST (subject to configured transient retries) and prints the saved generation ID/provider/model/status. It never runs automatically. It may consume quota; no live call is required for setup or tests.

## Tests and migrations

```sh
python -m pytest -q
python -m pip check
python -m alembic upgrade head
python -m alembic check
python -m alembic revision --autogenerate -m "describe schema change"
```

Review autogenerated migrations before applying. Tests migrate isolated temporary SQLite databases and mock provider responses. One test exercises actual Gemini SDK serialization against an offline HTTP transport. External sockets are blocked (loopback is permitted for Windows asyncio). No real API keys or paid endpoints are used. A read-only git check verifies frontend remains untouched.

## Security and limits

Never commit .env, API keys, local databases, or client-confidential materials. No authentication or reviewer assignment exists; run locally or behind appropriate access controls. Use synthetic or authorized scenarios. Do not send private legal client data to free-tier Gemini without authorization and a data-handling review. No web browsing, legal database lookup, citation verification, automatic correctness score, fine-tuning, embeddings, or RAG is implemented. Gemini cannot guarantee knowledge current to a supplied law date. Live model/key access must be checked by the optional manual smoke test.

