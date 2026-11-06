# CounselCheck connected frontend

Matte black and gold legal inquiry workspace with three researched reviewer reports, assessment follow-ups and a consented AI legal assistant placeholder for the future lawyer service.

Read [CONNECTED-SETUP.md](../CONNECTED-SETUP.md) for the complete Windows setup, keys, environment files, checks and Git workflow.

## Run

Use Node 24. In this directory:

```powershell
npm ci
npm run dev
```

Start the migrated Python backend on 127.0.0.1:8000 in a second terminal. Copy `.env.example` to ignored `.env.local`; the public settings are:

```dotenv
VITE_COUNSELCHECK_API_URL=http://127.0.0.1:8000
VITE_COUNSELCHECK_PREVIEW=false
```

Never put API keys in VITE_* variables. Every real model/search call happens on the backend. The frontend surfaces sanitized server errors.

For a free offline walkthrough use backend `AI_PROVIDER=mock` and `REVIEW_MODE=mock` while keeping browser preview false. This exercises the actual HTTP endpoints. Browser-only preview remains an optional isolated fixture and cannot make backend lawyer connections on its own.

## Workflow

Main chat generates a persisted answer and generation ID. Three reviewer requests use that ID to retrieve the actual answer. Expand each card to inspect queries, source text, exact evidence quotations, criterion scores, interpretations, correction/research needs and limitations. Incomplete, failed or abstaining reviewers produce no overall score. The lawyer CTA remains visible at every score and is emphasized below 70.

The scorer chat discusses existing persisted reports; it does not browse again or change the scores. Each inquiry and evaluation keeps its own messages. Historical browser-only previews may need a new answer or fresh review to obtain backend audit IDs.

The landing page, sidebar and Chats header allow direct AI legal assistant conversations without an inquiry. Linked connections offer separate processing and full-context sharing consent. With sharing enabled the backend stores the entire chosen inquiry snapshot including all messages, all assessments and scorer discussions; it is not limited to the selected answer. With sharing disabled no inquiry context is sent. The placeholder identifies itself as AI, not a real lawyer. Every subsequent message uses the consented snapshot plus the full server-side conversation. Revoking blocks future processing and removes the stored shared snapshot. Chat history remains saved, and snapshots do not automatically expand after consent.

Browser sessions use localStorage under `counselcheck:v1`; they are browser/origin local, not account synced. Backend generations/research/consented chat data are in your ignored SQLite database. A handoff bearer token is stored locally; do not share browser storage or tokens. Existing local-only lawyer chats require a new consented connection before sending.

## Checks

```powershell
npm run typecheck
npm test
npm run build
```

Existing packages provide Markdown rendering, icons and transitions. Do not manually edit generated `src/routeTree.gen.ts`.
