# CounselCheck

CounselCheck is a local hackathon MVP for asking legal questions, inspecting AI answers and researched assessments, collecting human expert judgments, and exporting evaluations as JSONL. It does not train models or send records to Mercor.

The connected workspace includes three automated reviewers and a consented AI legal assistant placeholder. Automated scores and model agreement do not establish legal correctness; human expert review is the source of verification, and reviewer identity is unverified in this MVP.

## What it does

- Generates and persists structured legal answers with jurisdiction and relevant law date.
- Runs three research assessments against the stored answer, using Groq models and Tavily evidence in live mode.
- Shows source text, evidence quotations, claim checks, limitations, and five weighted scoring criteria.
- Supports follow-up discussion of saved research reports without a new search.
- Offers separate consent for AI processing and sharing an inquiry snapshot with the AI legal assistant; supports closing conversations and revoking consent.
- Collects human evaluations through the benchmark API and exports one review per JSONL line.
- Provides deterministic mock generation and simulated research for an offline walkthrough without API keys.

## Stack and layout

| Location | Purpose |
| --- | --- |
| `frontend/` | React 19, TypeScript, TanStack Start/Router, Vite, Tailwind CSS, and Radix UI |
| `backend/app/api/routes/` | FastAPI HTTP endpoints |
| `backend/app/services/` | Generation, expert evaluation, research, and conversation logic |
| `backend/app/ai/` | Structured Gemini adapter, deterministic mock, and optional OpenAI adapter |
| `backend/app/db/` | SQLAlchemy models and SQLite sessions |
| `backend/alembic/` | Versioned database migrations |
| `backend/tests/` | Offline API, provider, consent, evidence, and persistence tests |
| `backend/tools/` | Configuration checks and connected HTTP smoke test |

## Run locally without API keys

Use Python 3.11+ and Node.js 24 with npm. Run the backend and frontend in separate terminals. The following commands are for macOS/Linux; Windows activation and configuration commands follow below.

### Backend

From the repository root:

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On first setup only, copy the environment template. Preserve an existing `.env`:

```sh
cp -n .env.example .env
```

Keep `AI_PROVIDER=mock` and `REVIEW_MODE=mock` for the offline demo. Apply migrations before starting the API:

```sh
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Optional fictional examples can be added before starting the server with `python -m app.seed` and `python -m app.demo seed`. Both commands are idempotent and make no model calls.

### Frontend

In a second terminal, from the repository root:

```sh
cd frontend
npm ci
cp -n .env.example .env.local
npm run dev
```

Copy the template only for initial setup. The public frontend settings should point to the backend:

```dotenv
VITE_COUNSELCHECK_API_URL=http://127.0.0.1:8000
VITE_COUNSELCHECK_PREVIEW=false
```

Keeping preview disabled exercises the actual backend, including server-side mock mode. Open the Local URL printed by Vite, normally `http://localhost:8080`. If its port changes, add that origin to backend `CORS_ORIGINS` and restart the backend.

On Windows PowerShell, activate the backend with `.venv\Scripts\Activate.ps1`. For initial configuration, use `Copy-Item .env.example .env` in `backend/` and `Copy-Item .env.example .env.local` in `frontend/`, only when those destination files do not already exist. See [the connected setup guide](CONNECTED-SETUP.md) for the detailed Windows workflow.

### Try the workflow

1. Start a new inquiry, select jurisdiction and law date, and enable the processing consent control.
2. Ask a fictional legal question. Mock answers and reviewer reports are explicitly simulated.
3. Expand the research reports to inspect criteria, evidence fields, and limitations; ask a follow-up about the assessment.
4. Open the AI legal assistant connection, choose processing and context-sharing consent separately, and send a message.
5. Use **Revoke consent & end** to block future processing and remove the stored shared snapshot.

The connected assistant is an AI placeholder, not a licensed lawyer. Direct conversations can be started without sharing an inquiry.

## Live provider configuration

All provider keys belong in the ignored `backend/.env`. Never place keys in `VITE_*` variables: those values are public browser configuration.

| Setting | Role |
| --- | --- |
| `AI_PROVIDER=gemini` | Enables Gemini for the main answer and connected follow-up conversations |
| `GEMINI_API_KEY` | Private Gemini credential |
| `GEMINI_MODEL` | Explicit model ID; the repository template selects `gemini-3.1-flash-lite` |
| `REVIEW_MODE=live` | Enables researched automated assessments |
| `GROQ_API_KEY` | Private credential for all three configured reviewer models |
| `TAVILY_API_KEY` | Private search and extraction credential |

The backend template also defines reviewer model IDs, timeouts, pacing, evidence limits, and context budgets. Restart the backend after changing configuration. Model availability and quota depend on the provider account; configured IDs are not silently substituted, and Gemini does not fall back to mock on failure.

From `backend/`, `python -m tools.check_setup` checks local configuration without making provider requests. The explicit `--providers` option requests provider model lists. Live generation and research consume provider quota; they are optional and never required for automated tests.

## APIs and data

With the backend running:

- Health: <http://127.0.0.1:8000/health>
- Interactive API documentation: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>
- Connected mode and configuration summary: <http://127.0.0.1:8000/api/legal/config>

`/api/legal` provides the connected answer, research review, report follow-up, handoff, AI legal assistant chat, revocation, and close endpoints. Research reports remain separate from human expert evaluation records.

`/api/v1` provides question creation/listing, fresh answer generation, generation retrieval, and expert evaluation submission/retrieval. `GET /api/v1/exports/evaluations` downloads JSONL with nested public question, generation, and evaluation records (`schema_version=1.1`). See [the backend README](backend/README.md) for request examples and error contracts.

Private reference answers and sources are excluded from generation input, public responses, and exports. Completed and failed generations are immutable; another generation creates a new record. Human verdicts support `correct`, `partially_correct`, `incorrect`, and `uncertain`; correction requirements apply to negative verdicts.

Automated assessments weight authority/citations at 30%, jurisdiction/date at 20%, interpretation/application at 25%, completeness at 15%, and clarity/qualification at 10%. An overall score requires all three reviewers to complete with scores. Scores are assessments, not accuracy probabilities or expert approval.

## Checks

From `backend/`, with the virtual environment activated:

```sh
python -m pytest -q
python -m alembic upgrade head
python -m alembic check
```

From `frontend/`:

```sh
npm run typecheck
npm test
npm run build
```

Backend tests use mocked providers/offline transports and temporary migrated databases. For an end-to-end HTTP walkthrough, start the backend in mock/mock mode and run `python -m tools.smoke_connected` from `backend/`. It refuses live calls unless explicitly enabled.

## Privacy and MVP limits

Keep the demo local, bind the API to `127.0.0.1`, and use fictional or authorized public material. There is no authentication or multi-tenant ownership system. Provider processing requires informed consent; information already sent to an external provider cannot be recalled by revoking a handoff.

Browser inquiry history and scoped bearer tokens persist in localStorage; backend records persist in SQLite. Do not share tokens or browser storage. Context-sharing snapshots are frozen at consent time; later inquiry messages are not automatically attached. Oversized full conversation contexts are rejected rather than silently trimmed.

Evidence quotation checks establish provenance within retrieved text, not that an authority is controlling, current, or correctly interpreted. Model citations are unverified. Human reviewer identities and qualifications are also unverified, and no enforced blind-review workflow exists.

Never commit private `.env` files, credentials, local databases, or confidential legal material. Production access controls and a real licensed-lawyer service are outside this MVP.

Further documentation: [backend](backend/README.md), [frontend](frontend/README.md), and [connected setup](CONNECTED-SETUP.md).
