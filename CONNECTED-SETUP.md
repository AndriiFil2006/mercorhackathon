# CounselCheck: complete Windows setup, pull, patch, keys, test and push

This patch is based on **your latest uploaded ZIP, commit f8a0f072619ffd00120739b90bc6d79c4074fb99**. Apply this patch after updating your existing repository. **Do not apply any earlier CounselCheck or standalone reviewer patch again.** This version connects the frontend, your teammate's Gemini main assistant, three researched reviewers, scorer follow-ups and the consented AI legal assistant (the temporary lawyer replacement).

The ZIP includes:

- `counselcheck-connected.patch`: all code changes relative to that latest upload.
- `START-HERE.md`: this entire guide.
- `CHANGED-FILES.txt`: exactly which files belong to the patch, for staging safely.
- `ENV-REFERENCE.txt`: a complete configuration reference containing empty keys, never a real secret.

No live keys, private `.env` files, databases, node_modules or venvs are included. Model/search calls run only when requested. Offline checks use fixtures, not live API quota.

## 0. Know what runs where

| Component | Service / location | Key |
|---|---|---|
| Main inquiry assistant | Existing Gemini adapter on the Python backend | `GEMINI_API_KEY` |
| Scorer follow-up conversation | Gemini, with the existing research reports as context | Same Gemini key |
| AI legal assistant / temporary lawyer | Gemini, with a consented server-side inquiry snapshot | Same Gemini key |
| Reviewer 1: authority focus | Groq, default `openai/gpt-oss-120b` | `GROQ_API_KEY` |
| Reviewer 2: jurisdiction/date focus | Groq, default `openai/gpt-oss-20b` | Same Groq key |
| Reviewer 3: interpretation/completeness focus | Groq, default `qwen/qwen3.8-27b` | Same Groq key |
| Independent searches and page extraction | Tavily, invoked separately by each reviewer | `TAVILY_API_KEY` |
| Browser | React frontend, http://localhost:8080 | No secret keys |
| Application API + Swagger | FastAPI, http://127.0.0.1:8000/docs | Backend loads private `.env` |

**Three keys total, not one key for every model.** You do not need OpenAI billing or a ChatGPT subscription for these model calls. Model availability and free quotas depend on your account and can change. Stay on free plans, do not enable billing or paid overages, and check the configured model IDs with the included setup tool. No silent paid fallback or model substitution is implemented.

The main Gemini adapter from your teammate is reused; the existing `/api/v1` benchmark endpoints remain intact. New `/api/legal` endpoints connect the current UI. No extra frontend dependencies were added.

## 1. Stop running servers and extract this download

In each terminal running `npm run dev` or Uvicorn, press **Ctrl+C**. Keep your source files.

Save `counselcheck-connected.zip` in your Windows Downloads folder. Extract it with File Explorer, or run in PowerShell:

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\counselcheck-connected.zip" "$env:USERPROFILE\Downloads\counselcheck-connected" -Force
```

The package is separate from your repository. Your repository remains:

`C:\Users\abhir\Downloads\mercorhackathon`

Do not replace that folder with a downloaded GitHub ZIP or create a second frontend/backend folder.

## 2. Preserve your work and pull your partner's latest version

Open the repository in VS Code. Press **Ctrl+`** to open a terminal. Run commands one at a time, not as one pasted batch that continues after failures.

```powershell
cd C:\Users\abhir\Downloads\mercorhackathon
git branch --show-current
git status
```

The instructions below assume your current branch is `main`, as in your earlier terminal output. If it shows a different branch, preserve that branch's work before switching to main. Do not delete branches or reset files.

If status says the tracked files are clean, skip the next commit. Untracked old patch ZIPs/markdown outside `frontend` and `backend` do not prevent a pull.

If you have frontend/backend changes you want to keep, first make sure private files are not already tracked:

```powershell
git ls-files -- backend/.env frontend/.env.local
```

That command must print **nothing**. If it prints a private filename, follow section 5's tracked-secret instructions before staging. Then preserve your source edits:

```powershell
git add frontend backend AGENTS.md
git diff --cached --name-only
git commit -m "Save current work before connected AI integration"
```

Inspect the staged filename list before committing: no real `.env`, keys, databases, or venv files should appear. Do not run `git add .` to scoop up unrelated files.

Make a backup branch for the current committed state, then fetch and pull:

```powershell
$backupBranch = "backup/before-connected-ai-" + (Get-Date -Format "yyyyMMdd-HHmmss")
git branch $backupBranch
git fetch origin
git pull --ff-only origin main
```

If the pull succeeds, continue. If it says fast-forward is impossible because you have local commits as well as your partner's commits, use a normal merge, preserving published history:

```powershell
git pull --no-rebase origin main
```

If a commit-message editor appears, save the default merge message and close it. In VS Code, use **Ctrl+S**, then close that editor tab. If a terminal Vim window appears, press **Esc**, type `:wq`, then press **Enter**.

If Git reports **CONFLICT**, stop here and inspect/send that output. Do not run the patch on an unresolved merge, use `--force`, choose one entire teammate version blindly, or reset the repository. The backup branch remains available; no forced history changes are needed.

## 3. Apply the new complete patch

Still at the repository root:

```powershell
git apply --check "$env:USERPROFILE\Downloads\counselcheck-connected\counselcheck-connected.patch"
```

**No output means it fits.** Then:

```powershell
git apply "$env:USERPROFILE\Downloads\counselcheck-connected\counselcheck-connected.patch"
git status
```

The status should list code and configuration-example changes plus new research/consent code. It will not create a private `.env` yet.

If the check fails, your partner may have changed matching files beyond the uploaded ZIP, or a prior patch may already be applied. Stop and send the error plus `git status`; do not force it. A clean application was verified against the exact uploaded snapshot. It cannot guarantee conflict-free application to later unseen changes.

## 4. Check Python and Node

```powershell
python --version
node --version
npm --version
```

Use Python **3.11+** and Node **24** for this project. If `python` is unavailable but `py` works, use `py -3.12 -m venv .venv` when creating the backend environment below. Node was already working in your earlier run.

## 5. Create your private environment files and prove Git ignores them

From the repository root:

```powershell
if (!(Test-Path .\backend\.env)) { Copy-Item .\backend\.env.example .\backend\.env }
if (!(Test-Path .\frontend\.env.local)) { Copy-Item .\frontend\.env.example .\frontend\.env.local }
git check-ignore -v backend/.env frontend/.env.local
git ls-files -- backend/.env frontend/.env.local
```

Expected: `git check-ignore` prints the matching ignore rule for both files; `git ls-files` prints **nothing**. Ignore rules are included at the repository root, and existing backend/frontend ignores are retained. Git ignore does not protect files that were previously tracked.

If `git ls-files` prints a private filename, untrack only that file while keeping its local contents:

```powershell
# Run only for a filename that git ls-files actually listed.
git rm --cached -- backend/.env
# If frontend/.env.local was also tracked:
git rm --cached -- frontend/.env.local
```

That removal belongs in your next commit. If any key was previously committed publicly, revoke it; ignoring or untracking does not remove it from past history. Never paste credentials into an issue, commit message or this conversation.

Open your local backend file:

```powershell
notepad .\backend\.env
```

It begins with mock/mock and blank keys. You can immediately test the entire connected UI using that configuration. The complete reference is shown below; it is safe to copy because it contains no keys:

```dotenv
AI_PROVIDER=mock
REVIEW_MODE=mock
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_TIMEOUT_SECONDS=60
GEMINI_MAX_RETRIES=1
GEMINI_MAX_OUTPUT_TOKENS=6000
AI_PROMPT_VERSION=legal-v1
GROQ_API_KEY=
REVIEW_MODEL_AUTHORITY=openai/gpt-oss-120b
REVIEW_MODEL_JURISDICTION=openai/gpt-oss-20b
REVIEW_MODEL_REASONING=qwen/qwen3.8-27b
REVIEWER_TIMEOUT_SECONDS=90
REVIEWER_MAX_OUTPUT_TOKENS=4000
GROQ_MIN_INTERVAL_SECONDS=60
TAVILY_API_KEY=
REVIEW_SEARCH_QUERIES=1
REVIEW_SOURCES_PER_QUERY=2
REVIEW_SOURCE_CHARS=3000
REVIEW_CACHE_SECONDS=3600
CHAT_CONTEXT_MAX_CHARS=180000
DATABASE_URL=sqlite:///./legal_eval.db
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

Save with **Ctrl+S** and close Notepad. The filename must be `.env`, not `.env.txt`. If you already had a `.env`, merge these settings instead of deleting other settings you need.

Now open the frontend settings:

```powershell
notepad .\frontend\.env.local
```

Ensure these exact values are present:

```dotenv
VITE_COUNSELCHECK_API_URL=http://127.0.0.1:8000
VITE_COUNSELCHECK_PREVIEW=false
```

Save. **false is important:** the browser must call the connected backend even when the backend itself runs in mock mode. Browser-only preview skips the backend. Never put a Gemini/Groq/Tavily key in any `VITE_*` variable: Vite exposes those variables to the browser.

If earlier instructions led you to set API environment variables in PowerShell, those can override `.env`. Clear only the relevant overrides in the terminal where you will launch the backend:

```powershell
Remove-Item Env:AI_PROVIDER,Env:REVIEW_MODE,Env:GEMINI_API_KEY,Env:GEMINI_MODEL,Env:GROQ_API_KEY,Env:TAVILY_API_KEY -ErrorAction SilentlyContinue
```

This changes this terminal's environment, not the `.env` file or system settings. Start a fresh terminal if other old settings still override the file. Backend settings are cached, so restart Uvicorn after editing `.env`.

## 6. Install and start the backend in offline mode first

In terminal A:

```powershell
cd C:\Users\abhir\Downloads\mercorhackathon\backend
if (!(Test-Path .\.venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m tools.check_setup
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The migration creates research-audit and consented-handoff tables while preserving existing question, generation and expert-evaluation records. The code does not silently create tables on startup. Do not delete your existing database to fix a migration error; send the error instead.

Open:

- http://127.0.0.1:8000/health — should show healthy.
- http://127.0.0.1:8000/api/legal/config — mode/model names and key-presence booleans, never key values.
- http://127.0.0.1:8000/docs — Swagger for existing and newly connected APIs.

Keep terminal A running.

## 7. Start the frontend in another terminal

In VS Code, press **Ctrl+Shift+`** for a new terminal (terminal B):

```powershell
cd C:\Users\abhir\Downloads\mercorhackathon\frontend
npm ci
npm run dev
```

Open the Local URL, normally http://localhost:8080. Leave terminal B running. Use `npm.cmd` instead of `npm` if PowerShell blocks npm.ps1.

If npm reports EPERM/unlink on a `.node` file, another dev server may still hold it. Stop only this project's running servers with Ctrl+C, close other terminals using it, then retry `npm ci`. If it remains locked, restart Windows before reinstalling; do not run `npm audit fix --force` as an installation fix. Avoid changing dependency versions during integration.

If Vite chooses a port other than 8080, either stop the older server using 8080, or add the printed frontend origin to backend `CORS_ORIGINS` and restart the backend. A backend CORS/network error does not mean the patch failed.

## 8. Verify the entire mock flow through the frontend

1. Begin a **New inquiry**. Choose jurisdiction and law date.
2. Tick the external-processing/research consent checkbox. In mock mode no external call actually occurs; the same consent control is exercised.
3. Ask a fictional legal question and send it. A clearly labeled SIMULATED answer should appear.
4. The three reviewer cards should complete with fixture scores 58, 72 and 64; overall 65. These are interface test fixtures, not findings about legal correctness.
5. Expand **Research, evidence and score breakdown**. It shows five criterion scores, claims, limitations and the source record. Mock mode explicitly contains no real searched sources.
6. Ask the assessment team a follow-up. It should respond through the backend's mock conversation wrapper. Scorer chat is unavailable before an answer and a completed/abstained assessment exist.
7. Click **Connect to a lawyer**. The next screen clearly identifies the AI legal assistant placeholder. Give processing consent and, if desired, separately opt in to sharing the **entire inquiry and reviewer snapshot**.
8. Open the chat and send a message. The AI placeholder should return a mock reply. Refresh, navigate to Chats and reopen the conversation: your browser history persists.
9. Use **Revoke consent & end**. The backend blocks further processing and removes its stored shared snapshot. Existing chat history remains locally viewable; information already processed by an external provider cannot be recalled.
10. Test direct access from the landing page, sidebar, or Chats header. You can create an AI legal assistant conversation without an existing main inquiry or assessment; no inquiry context is attached.

The legal-assistant snapshot includes all accepted messages and **all assessments in the chosen inquiry**, not only the selected answer: scores, criteria, source text, claim checks, limitations, expert feedback and scorer follow-ups. It is frozen at the time of consent. Later inquiry messages or later-finishing reviews are not silently added. To share a newer snapshot, create a new consented connection from that inquiry.

## 9. Run automated checks and optional HTTP smoke

In a third terminal, from backend/:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m tools.smoke_connected
```

The smoke command expects the server to already run on 8000 in mock/mock mode. It exercises the main answer, all three reviewer requests, scorer chat, full handoff, AI lawyer reply and revocation over HTTP. It refuses to call live services unless you explicitly request live mode.

From frontend/:

```powershell
npm run typecheck
npm test
npm run build
```

The added automated tests use offline transports/mocks and temporary databases, even if your local `.env` contains keys. Live-provider acceptance is not claimed by those tests.

## 10. Get the three free keys

### Gemini: main chat, scorer follow-up and AI lawyer

1. Visit https://aistudio.google.com/apikey and sign in with your own eligible Google account.
2. Revoke/delete the Gemini key you pasted into the earlier conversation, then create a new key in a free-tier project.
3. Do not link paid billing just for this hackathon. Check your project is on the free tier and has quota for `gemini-3.1-flash-lite`.
4. Copy the replacement key directly into **your local** `backend/.env` after `GEMINI_API_KEY=`. Do not send it to a teammate through Git or place it in the frontend.

The current official pricing page lists free input/output tokens for Gemini 3.1 Flash-Lite, subject to project limits. Its free tier does **not** include Google Search grounding, so this patch uses Tavily for reviewer web research instead. Free-tier content may be used to improve provider products; use fictional/public material for the demo.

Sources: https://ai.google.dev/gemini-api/docs/pricing and https://ai.google.dev/gemini-api/docs/rate-limits. Key setup: https://ai.google.dev/gemini-api/docs/api-key.

### Groq: three different reviewer models with one key

1. Sign up at https://console.groq.com/.
2. Stay on the **Free** plan; do not upgrade to the paid Developer tier.
3. Open https://console.groq.com/keys and create a key.
4. Put it after `GROQ_API_KEY=` in your local backend `.env`.
5. Check your account-specific limits at https://console.groq.com/settings/limits. If that URL redirects, use Console Settings → Limits.

The configured model candidates are GPT-OSS 120B, GPT-OSS 20B and Qwen3.8 27B. These are three distinct model IDs, but the two GPT-OSS models are related, and all reviewers can share errors. Active catalog entries do not guarantee that every model has free quota on every account. The setup command in section 11 lists available IDs. If a candidate is unavailable, choose another **distinct text-generation model with free access in your account**, edit only that reviewer model variable and restart. Do not substitute the same model three times or enable paid billing to bypass a quota error. Ask for help selecting a replacement if no third eligible model is available.

Official model catalog: https://console.groq.com/docs/models; rate limits: https://console.groq.com/docs/rate-limits; plan distinction: https://console.groq.com/docs/billing-faqs.

### Tavily: searches and retrieved legal pages

1. Sign up at https://app.tavily.com/.
2. Use the free Researcher plan and copy an API key from the dashboard.
3. Put it after `TAVILY_API_KEY=` in local backend `.env`.
4. Leave pay-as-you-go/paid overage **disabled**. The currently advertised free plan includes 1,000 credits/month without a credit card.

At the default settings, each of the three reviewers performs one Basic search (normally one credit each). A bounded Basic Extract request may also be used for search results without page text. Extraction can consume additional credits. Identical recent reports are cached for one hour; clicking Retry forces fresh research and can use quota. Groq free token-per-minute limits may be reached before Tavily's monthly search credits. By default the backend spaces successive calls to the SAME model by 60 seconds and serializes model calls. Three researched reports may take roughly 1–4 minutes; this is intentional free-tier pacing, not a frozen UI. If the account has higher free limits you may deliberately lower `GROQ_MIN_INTERVAL_SECONDS`; do not raise billing. Large answers or an especially small quota can still require waiting or a different eligible model.

Official pricing: https://www.tavily.com/pricing. Search/extraction documentation: https://docs.tavily.com/documentation/api-reference/endpoint/search and https://docs.tavily.com/documentation/api-reference/endpoint/extract.

### Do I need MCP?

No MCP installation is needed to run this application. MCP is a protocol for exposing tools; it does not itself supply free searches or model access. Here the Python backend invokes Tavily's HTTP Search/Extract APIs, so all three reviewers can research without an editor plugin.

If you independently want Tavily tools inside VS Code or another supported MCP client, see https://docs.tavily.com/documentation/mcp and use its remote server https://mcp.tavily.com/mcp/ with the documented sign-in process. That editor integration is optional and does not wire itself into this application or create unlimited free quota.

## 11. Enable live mode and check configuration without revealing keys

Stop terminal A's backend with Ctrl+C. Edit `backend/.env` in Notepad. Change only these mode values, keep the other settings, and fill in your three private keys:

```dotenv
AI_PROVIDER=gemini
REVIEW_MODE=live
GEMINI_API_KEY=YOUR_NEW_PRIVATE_GEMINI_KEY
GROQ_API_KEY=YOUR_PRIVATE_GROQ_KEY
TAVILY_API_KEY=YOUR_PRIVATE_TAVILY_KEY
```

Replace the placeholder key values with actual keys locally. Do not put the word `YOUR_...` in a key value you expect to work. Keep `GEMINI_MODEL=gemini-3.1-flash-lite` and `AI_PROMPT_VERSION=legal-v1` unless you deliberately select another supported model/prompt.

From backend/:

```powershell
.\.venv\Scripts\python.exe -m tools.check_setup
.\.venv\Scripts\python.exe -m tools.check_setup --providers
```

The first command checks local file protection and key-presence booleans. The second explicitly requests Gemini/Groq model lists using server-side keys; it does not generate model output or run a Tavily search. It prints model availability and HTTP status, never secrets. A model-list success does not guarantee remaining generation quota.

If your selected Gemini model or one Groq reviewer ID is absent, fix that model variable before continuing. Do not silently switch providers or upgrade billing. For an unavailable Groq model, copy a suitable active, free-account-eligible text model ID from the printed list into the appropriate `REVIEW_MODEL_...` line, keeping all three distinct.

Start the backend again:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave it running. Restart `npm run dev` if you edited frontend `.env.local`. Start a **new inquiry** in the browser: historical mock answers intentionally cannot be submitted for live model evaluation. The Gemini main answer should arrive first, then three researched reviewer cards. Per-reviewer errors explain missing configuration, unavailable models, invalid evidence, timeouts or quota limits; no score is substituted.

For one explicit live end-to-end HTTP test with fictional facts, from backend/ in another terminal:

```powershell
.\.venv\Scripts\python.exe -m tools.smoke_connected --live --consent-external
```

This consumes free Gemini, Groq and Tavily quota. It is optional and never runs automatically. It uses the generated main answer, collects three reviews, asks a scorer follow-up, creates a consented legal-assistant conversation and revokes the handoff afterward. The bearer token is never printed. If a free model fails, inspect that error rather than repeatedly retrying all services.

## 12. Exactly what each reviewer returns and how scoring works

Each reviewer uses its own configured model and perspective, generates focused public legal queries, searches online, obtains page text where available, and evaluates the **stored main-AI answer**. The browser sends its generation ID; the backend fetches the stored answer and public question context instead of trusting a tampered client copy. Pasted external answers remain supported but are marked `client_supplied_answer`.

The research record includes:

- Search queries and retrieval timestamps.
- Retrieved source URLs/titles/text, extracted-page vs search-excerpt provenance, and whether model context was capped.
- Specific claims from the main answer, supported/contradicted/incomplete/unresolved verdicts, exact quoted evidence and interpretations.
- Jurisdiction and law-date analyses, including what could not be established.
- Five criterion scores with explanations, limitations, suggested corrections or research still needed, and a conclusion.

The server validates the output schema, known source IDs and quote presence in the retrieved source text. A scored live report requires quoted evidence and at least one extracted page; a false quotation is rejected. These checks establish evidence provenance, **not** that the source controls, is current, was interpreted correctly, or covers every relevant legal authority. The user sees the actual evidence record used by the model, not an assurance of exhaustive legal research. Page text is capped per source (3,000 characters by default) and visibly marked when capped. Full client chat handoffs are never silently trimmed; oversized requests are rejected.

| Criterion | Weight |
|---|---:|
| Supporting authorities/citations | 30% |
| Jurisdiction and relevant date | 20% |
| Interpretation/application | 25% |
| Completeness | 15% |
| Clarity/qualification | 10% |

Each model scores all five criteria from 0–100. The backend calculates:

`round-half-up((30*authority + 20*jurisdiction + 25*interpretation + 15*completeness + 10*clarity) / 100)`

Overall = round-half-up(mean of all three completed model scores). The frontend uses matching rounding for the nonnegative scores and explains the score spread. If any reviewer errors or abstains, the overall remains unavailable. **Below the displayed 70 threshold** emphasizes connecting to a real lawyer; at 70 or above the connection stays available as a secondary action. The connected service is currently an explicitly labeled AI placeholder, so do not describe it as human legal assistance in a demo.

70 is a product decision, not a validated accuracy probability or safety guarantee. Agreement between AI models is not expert verification. Automated reports are kept separate from the existing human-expert evaluation records.

## 13. Consent, persistence and what is not production-ready

At `/connect`, the client separately chooses external AI processing and whether to share the entire inquiry snapshot. If sharing is unchecked, no inquiry snapshot is sent. Direct connections work with no inquiry. Handoff creation saves the snapshot and consent flags on the backend but makes no model call; the first legal-assistant message is the first time that model receives it. Every subsequent turn receives the same consented snapshot plus full stored legal-assistant conversation.

The server issues a random bearer handoff token and stores only its hash, alongside the private snapshot/messages/consent timestamp. It is not placed in URLs. Revoking the token removes the snapshot and blocks future processing. A response already in progress is discarded if revocation occurs before completion, but information already sent to a provider cannot be recalled. Leaving a chat ends it while preserving history. Refreshing the page preserves browser chats and the scoped handoff token.

This local hackathon backend still has no user authentication or multi-tenant ownership system. A consent checkbox/bearer receipt is not independently authenticated proof of a person's identity or rights to another person's data. Keep Uvicorn bound to 127.0.0.1, use fictional/public data, and do not deploy this as a public legal service without access controls, stronger consent/auditing, privacy review and qualified legal review. Free provider data policies must be considered before sending sensitive material.

## 14. Commit and push the integrated changes

You can leave servers running and use another terminal, or stop them with Ctrl+C. From the repository root:

```powershell
cd C:\Users\abhir\Downloads\mercorhackathon
git status
git check-ignore -v backend/.env frontend/.env.local
git ls-files -- backend/.env frontend/.env.local
```

Again, the `git ls-files` command must print nothing. Stage only files in this patch's manifest:

```powershell
Get-Content "$env:USERPROFILE\Downloads\counselcheck-connected\CHANGED-FILES.txt" | ForEach-Object { git add -- $_ }
git diff --cached --name-only
git diff --cached --stat
```

`.env.example` is safe to stage because it contains empty key placeholders. `backend/.env`, `frontend/.env.local`, real keys, databases, `.venv` and `node_modules` must not appear. Do not print a full private `.env` into a terminal transcript or screenshot.

If the staged file list is correct:

```powershell
git commit -m "Connect Gemini chats, online reviewers and consented AI legal assistant"
git push origin main
```

A successful push ends with a line like `main -> main`. Verify:

```powershell
git status
```

It should say your branch is up to date with `origin/main`. If your partner pushed more commits while you worked and the push is rejected, preserve your commit and merge the newest main:

```powershell
git pull --no-rebase origin main
git push origin main
```

Stop for any merge conflict and resolve it deliberately; never force push. Your partner receives the code and blank `.env.example` templates. They must create their own ignored local files and supply their own keys. Your private `.env` will not be uploaded as long as it remains untracked and ignored.

## 15. Quick troubleshooting

| Symptom | Action |
|---|---|
| Main assistant says backend unreachable | Start Uvicorn on 8000; confirm `/health`; check frontend API URL and CORS origin. |
| UI still shows browser-only preview replies | Set `VITE_COUNSELCHECK_PREVIEW=false`; restart Vite. |
| Replies remain MOCK after editing backend `.env` | Restart Uvicorn and inspect `/api/legal/config`; clear stale terminal environment overrides. |
| Gemini key invalid/leaked/quota error | Replace with a new private free-tier key or wait for quota reset. Do not reuse the key disclosed earlier. |
| Reviewer model unavailable | Run setup check `--providers`, select a suitable distinct model available on the free account, restart. |
| Tavily unavailable or no sources | Check key/free credits, use a more specific question/jurisdiction/date; retry only the affected reviewer. |
| Reviewer abstained | Read its evidence gaps; there is no defensible overall score until those are resolved. |
| Invalid quotation / structured output | Retry the affected reviewer; no fake score or automatic repair call is used. |
| Scorer chat has no backend report | Generate/review a new answer or retry its reviewer; old browser-only preview reports have no persisted audit ID. |
| Old lawyer chat has no token | Use Reconnect with consent; old local-only chats cannot silently acquire sharing consent. |
| Consent token missing after database reset | Start a new consented connection; the old backend receipt no longer exists. |
| Context too large | No full-chat data was silently dropped. Start a new inquiry/conversation, or deliberately raise the configured budget within provider limits. |
| EPERM during npm ci | Stop processes holding this project's native Node modules, then retry. |
| Patch does not apply | Stop; verify latest source/previous patch state and send error output. |
