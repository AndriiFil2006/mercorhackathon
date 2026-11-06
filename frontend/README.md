# CounselCheck

Matte black and dark gold legal inquiry workspace with three independent reviewer cards, assessments, lawyer connection preview, saved chats, expert feedback and JSONL export.

## Run

Use Node.js 24. From `frontend/`:

```powershell
npm ci
npm run dev
```

Open the Local URL printed by Vite (normally http://localhost:8080). Leave the terminal running. Ctrl+C stops it. Use `npm.cmd` if PowerShell blocks npm.ps1. TanStack regenerates its route tree when Vite starts; do not edit `src/routeTree.gen.ts` manually.

## Walk through the frontend before the backend is ready

Create `frontend/.env.local` with:

```dotenv
VITE_COUNSELCHECK_PREVIEW=true
```

Restart the dev server. Preview mode gives an illustrative answer and three visibly labeled fixture assessments averaging 65/100. It does not make model calls or perform searches. Placeholder lawyer connections and chat messages are local previews, not real matches or delivered messages. Remove this setting or set it to false when integrating the backend.

The normal mode calls your backend. If it is unavailable, the interface displays a retryable error without fabricating an answer or a score.

## Backend handoff

Implement the API boundary in `src/lib/legal/api.ts`. No API keys belong in the frontend. The backend must own model access, online research, citation validation, rate limits and credentials, following the existing gateway setup where applicable. The frontend launches three requests in parallel. The backend must assign three distinct model configurations; a reviewer role label alone does not imply a different model.

Use same-origin `/api/legal/answer` and `/api/legal/review`, or set `VITE_COUNSELCHECK_API_URL` to your backend's origin and allow the frontend origin in its CORS configuration. Restart Vite after changing environment variables. The frontend request timeout is 60 seconds.

### POST /api/legal/answer

Request: `{question, jurisdiction, lawDate, messages}`. Messages are previous conversation turns containing `{id, role, text}`; the new question is separately supplied in `question`.

Response:

```json
{ "answer": "Markdown legal answer with supporting citations" }
```

### POST /api/legal/review

Request: `{reviewer, question, answer, jurisdiction, lawDate}`. The reviewer is `authority`, `jurisdiction`, or `reasoning`.

Response:

```json
{
  "model": "Actual model identifier",
  "score": 82,
  "explanation": "Why this answer earned this score",
  "findings": ["A specific issue found or a supported aspect of the answer"],
  "sources": [{ "title": "Authority title", "url": "https://official-source.example/path" }]
}
```

The three review purposes are authority/citation validity, jurisdiction/date applicability, and reasoning/completeness. Return real research findings and actual source links, not invented authorities. Scores must be numeric and within 0–100; invalid responses show an error. Scores reflect model judgments, not established legal correctness. The overall score is the rounded arithmetic mean only after all three distinct reviewers complete. Failed reviewers can be retried individually.

At a displayed overall score below 70, the lawyer connection action is prominent. At 70 or above, it remains available as a secondary action. While scores are pending, the secondary connection remains accessible.

### Lawyer services

`/connect?session=...&evaluation=...` intentionally uses a placeholder lawyer, Alex Morgan, clearly labeled. It creates a browser-local conversation and links to `/chats?chat=...`. No real lawyer is contacted and no messages are delivered. To make this live, replace the placeholder connection and local chat operations in `src/components/legal/LawyerChats.tsx` with authenticated directory/matching, lawyer identity verification, message transport and server persistence. Do not present this placeholder as a registered or verified lawyer.

The always-accessible Chats navigation lists all conversations, including ended chats. Leaving a chat makes it read-only and keeps its history. Returning to an inquiry restores its session. Deleting an inquiry retains its lawyer chats and indicates that the original context is unavailable.

## Saved data and export

The `counselcheck:v1` localStorage key stores sessions, jurisdiction/date, messages, all answer assessments, submitted expert evaluations, active inquiry, sidebar preference and lawyer chats. The earlier transfer workspace's storage is untouched. Conversations are browser/origin local, not account synced. Reloading interrupts in-flight calls; unfinished reviews show a retry action. A browser-storage warning appears if persistence fails.

Jurisdiction/date lock once an answer assessment exists; use a new inquiry for different legal context. A dropdown selects earlier assessments without overwriting them. Expert feedback collects reviewer name, verdict, error categories, explanation, correction, supporting authority and confidence. JSONL export includes the question, answer, three model assessments, overall score, provenance and expert feedback. A typed name does not authenticate an expert; export uses `expert_feedback_submitted`, never `expert_verified`, and marks preview provenance. Your backend must handle expert identity, adjudication, rights and quality gates before treating records as validated training data.

## Checks

After Vite has generated the route tree:

```powershell
npm run typecheck
npm test
npm run build
```

Existing React, Lucide, React Markdown, Tailwind and animation packages support this update; no extra package installation beyond `npm ci` is necessary. Navigation and cards use short fade/slide transitions, with reduced-motion support.
