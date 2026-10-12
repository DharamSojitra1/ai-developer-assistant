# AI Developer Assistant — Frontend

A React + TypeScript + Vite web app for the FastAPI **AI Developer Assistant** backend. It provides authenticated chat (an agent mode and a fast streaming mode), a knowledge base for RAG documents, and a usage dashboard.

It only talks to the endpoints the backend already exposes; nothing in the connected app is mocked.

## Requirements

- Node.js 20.19+ (or 22.12+) and npm
- The backend running locally (see the repository root README), by default on `http://localhost:8000`

## Getting started

```bash
cd frontend
npm install
cp .env.example .env   # optional — the defaults work for local development
npm run dev            # http://localhost:5173
```

During development the Vite server proxies every `/api` request to `VITE_DEV_API_TARGET`, so the browser sees one origin and CORS is not involved.

To try the UI without spending LLM credits, start the backend with `MOCK_MODE=true`. Fast stream mode then returns mock text. Agent mode still calls the real model, because the agent ignores `MOCK_MODE`.

## Scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | Start the dev server with hot reload |
| `npm run build` | Type-check, then build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Run ESLint |
| `npm run typecheck` | Run the TypeScript compiler only |
| `npm run test` | Run the Vitest suite once |
| `npm run test:watch` | Run Vitest in watch mode |

## Environment variables

Every `VITE_*` variable is compiled into the public JavaScript bundle. **Never put Groq API keys, JWT signing secrets, or any backend secret here.** `.env` and `.env.*` are git-ignored; only `.env.example` is committed.

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | empty (same origin) | Backend origin used for production builds. Leave it empty when a reverse proxy serves the app and `/api` from one origin. |
| `VITE_DEV_API_TARGET` | `http://localhost:8000` | Where the dev server proxies `/api` (development only). |

### Production deployment

- **Same origin (recommended):** serve `dist/` and route `/api` to the backend from one reverse proxy, and leave `VITE_API_BASE_URL` empty. Configure the proxy to fall back to `index.html` for client-side routes (`/knowledge`, `/usage`, …).
- **Separate origins:** set `VITE_API_BASE_URL` to the backend origin, and set the backend's `FRONTEND_URL` to the frontend's origin so CORS allows it.

## Features

- **Auth:** register, sign in, sign out, and protected routes.
  - Expired sessions redirect to sign-in and return to the page you were on afterwards.
  - Tokens refresh automatically, both before they expire and when a request comes back 401.
- **Chat:**
  - **Agent** mode (default) calls `POST /api/agent/chat`. Replies show the route, the status, and sources grouped by document. Tool actions that need approval show an Approve/Reject card.
  - **Fast stream** mode streams `POST /api/chat/chat/stream` token by token, and you can stop it partway.
  - Markdown, GitHub-flavored tables, syntax-highlighted code with copy buttons, retry, and smart auto-scroll.
  - The composer stops duplicate submissions.
- **Conversations:**
  - The sidebar lists one entry per conversation, grouped by when it was last active. Entries can be deleted, and "Clear history" removes everything.
  - Each conversation has its own URL (`/c/<id>`), so reloading the page or sharing a link reopens it. Reopened conversations can be continued.
  - The assistant only uses earlier messages from the same conversation as context, so "New chat" really starts fresh.
- **Knowledge base:**
  - Upload `.txt`, `.md`, or `.pdf` files (up to 5 MB) or paste text.
  - Run semantic search with scores, and delete documents.
  - Documents indexed from this browser are remembered locally, because the backend has no endpoint that lists documents.
- **Usage:** daily requests, input and output tokens, and estimated cost over 7, 30, or 90 days.
- **Layout and accessibility:**
  - Responsive layout with a collapsible desktop sidebar and a mobile drawer.
  - Keyboard support, visible focus rings, ARIA live regions, and reduced-motion support.

## Security notes

- Model output is rendered as Markdown with raw HTML disabled, so no `dangerouslySetInnerHTML` is used.
  - Images become plain links.
  - Links open with `rel="noopener noreferrer nofollow"`.
- Server-side failures (5xx) and network errors are always shown as fixed, friendly messages, so internal details never reach the screen.
  - Only the backend's user-facing 4xx messages are shown, for example "email already registered".
  - Tool arguments are never displayed.
- The access token lives only in memory.
  - The refresh token is kept in `localStorage` so sessions survive reloads, because the backend returns it in the JSON body.
  - This is the trade-off: an XSS bug could read it. Rendering is locked down to reduce that risk. An httpOnly cookie issued by the backend would be stronger (see below).
- Refreshes are single-flight and coordinated across tabs (Web Locks). A rotated refresh token is never reused.
- Post-login redirects only accept same-app paths, which prevents open redirects.

## Project structure

```
src/
  api/          HTTP client, token refresh, error normalization, typed endpoint functions
  auth/         Token store, AuthProvider, route guard
  components/   UI primitives, layout (sidebar, drawer, top bar), Markdown renderer
  features/
    auth/       Sign-in and registration pages
    chat/       Chat session state, composer, messages, agent UI (sources, approvals)
    history/    Conversation history sidebar
    knowledge/  Upload, paste, search, and delete documents
    usage/      Usage dashboard
  hooks/ lib/   Small shared utilities
  styles/       Tailwind theme tokens and Markdown styles
```

## Backend gaps

The frontend works around these limitations. Each one needs backend work before the corresponding feature can be fully supported:

1. **Streaming has no metadata.** `/api/chat/chat/stream` returns plain text, so streamed replies cannot show sources, routes, tool steps, or approvals.
2. **No document listing.** There is no `GET /api/rag/documents`, so the Manage tab can only list documents indexed from the current browser, plus deletion by ID.
3. **No current-user endpoint.** Without `/api/auth/me`, the UI shows the email entered at sign-in and cannot show the user's role.
4. **Refresh token is returned in JSON.** An httpOnly, `SameSite` cookie set by the backend would keep it out of reach of JavaScript.
5. **CORS for cross-origin deployments.** The backend does not expose `X-Agent-Run-ID` or `X-Conversation-ID` (or any response header), and `allow_methods` omits `PUT`/`PATCH`. Neither is needed today, but both would matter for future features.
6. **The agent ignores `MOCK_MODE`.** Local agent testing always calls the real LLM.
