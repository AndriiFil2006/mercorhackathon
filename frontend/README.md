# Untitled — transfer workspace

A matte black and lavender interface with a transfer assistant, a separate checker, and saved conversation sessions. “Untitled” is a placeholder name.

## Run locally

Use Node.js 24 and npm (tested with Node 24.22.1). In the folder containing package.json:

    npm ci
    npm run dev

Open the Local URL printed in the terminal, normally http://localhost:8080. Stop the server with Ctrl+C. If port 8080 is occupied, use the URL Vite prints.

If PowerShell blocks npm.ps1, use npm.cmd instead of npm in the commands.

## Put this update into the GitHub repository already open in VS Code

1. Open the VS Code terminal with Ctrl+backtick. Confirm you are in the frontend folder containing package.json. Use pwd to see the path.
2. Before copying files, run:

       git status
       git pull --ff-only
       git switch -c ui/matte-workspace

   Begin from a clean working tree. If there are already uncommitted teammate changes, preserve/commit them before replacing matching files. If git status says this is not a Git repository, use the Command Palette (Ctrl+Shift+P), choose Git: Clone, enter the existing repository URL, and open the cloned folder.

3. Extract this ZIP outside the repository. Open the extracted transfer-workspace folder. Copy its contents into the existing frontend folder, replacing matching files; do not put the whole transfer-workspace directory inside the frontend by accident. Do not delete existing files or replace the repository's .git directory, environment files, or additional backend folders.

   If the repo has already advanced beyond the uploaded snapshot, copy/merge the changed files listed below instead of overwriting newer files wholesale. In particular, preserve your teammate's real model integration in src/lib/transfer/api.ts: our changes to that file only simplify the disconnected placeholder messages. No AI function signatures were changed.

4. In the existing frontend folder, run:

       npm ci
       npm run dev

5. Open the printed URL. Check the landing page, New session, sidebar collapse, switching sessions, and refreshing the browser. Ctrl+C stops the development server.
6. Run the checks:

       npm run typecheck
       npm test
       npm run build

7. Review and commit from that same repository:

       git status
       git diff --stat
       git diff
       git add src public package.json package-lock.json README.md
       git commit -m "Refine matte UI and add saved sessions"
       git push -u origin ui/matte-workspace

   Stage only the frontend paths if this is a monorepo. The push uploads the new branch to the existing origin; it does not create a different repository. Open a pull request into your team's working branch (usually main). Merging that pull request makes the update available on the shared branch. Do not force push.

   If you are intentionally committing directly to an existing shared branch, skip git switch -c and use git push after committing. Keep pushed history intact.

## What changed

- Flat, neutral black/charcoal surfaces with separate matte lavender/purple accents.
- No grid background, gradient wash, purple glow, landing preview, example CTA, or planning-only badges.
- A minimal landing page, placeholder branding, and one Get started action.
- A collapsible desktop sidebar and mobile session drawer.
- New sessions, automatic conversation titles, switching, renaming, and deleting.
- Both assistant conversations, reports, reviews, and the selected session survive refresh.
- Independent sessions keep background responses in the originating conversation.
- Clean workspace header; no demo dropdown or request/context button.
- Compact mobile assistant tabs and independent desktop panels.
- Working clipboard feedback, report export, paste-report dialog, and retry controls.
- An npm lockfile for reproducible installation.

## Changed or added project files

- src/styles.css
- src/routes/index.tsx
- src/routes/workspace.tsx
- src/routes/__root.tsx
- src/components/transfer/MainPanel.tsx
- src/components/transfer/CheckerPanel.tsx
- src/components/transfer/shared.tsx
- src/components/transfer/SessionSidebar.tsx (new)
- src/lib/transfer/useSession.ts
- src/lib/transfer/sessionStorage.ts (new)
- src/lib/transfer/useSession.test.tsx (new)
- src/lib/transfer/api.ts (placeholder copy only)
- public/favicon.svg (new)
- package.json (typecheck command)
- package-lock.json (new)
- README.md

The route tree is generated automatically by TanStack; do not edit it manually.

## Sessions

Sessions are saved in localStorage in the current browser, under transfer-workspace:v1. This includes messages, context, reports, and review history. The active session and collapsed-sidebar preference are saved too.

This is device/browser-local history, not account-based cloud synchronization. Use the same local origin when testing: localhost and 127.0.0.1 have separate browser storage. Clearing site data removes saved sessions. A page reload interrupts in-flight model requests; saved partial messages remain visible and interrupted reviews can be retried.

## AI integration for your teammate

Connect the existing async boundaries in src/lib/transfer/api.ts:

- generateReport: main conversation and response streaming.
- reviewReport: automatic review of a completed or pasted report.
- askChecker: independent follow-up questions in the checker panel.

The uploaded starter has no live AI backend. That remains the case in this update. It saves requests and reports but does not generate real AI plans or verdicts until those functions are connected. Existing fixture data remains available internally, with its labels; demo controls have been removed from the interface.

Keep credentials on the server. The app's free-form Markdown display and report/review IDs are retained for integration.

## Validation

The production build, TypeScript check and automated tests were run. Browser interaction checks cover desktop and mobile layouts, creating and switching sessions, refreshing saved history, collapsing/expanding the sidebar, renaming/deleting conversations, and pasting reports. The source archive does not include node_modules or build artifacts; install dependencies with npm ci.

This project retains its original Lovable/TanStack configuration and AGENTS.md instructions.
