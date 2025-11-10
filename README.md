# EasyForm

AI-powered form filling across the web. EasyForm combines a modern React frontend, a FastAPI backend with a three-agent orchestration pipeline, and a Manifest V3 browser extension that analyzes pages and fills forms automatically from rich user context using RAG.

Interactive API docs are exposed at `/api/docs` once the backend is running. The health probe lives at `/api/health`.

## What EasyForm does

- Analyze any web page and detect form fields reliably
- Generate context-aware values using AI (supports PDFs, images, clipboard text as context)
- Execute safe, scripted actions in the browser (fill inputs, check radios/checkboxes, select dropdowns, click buttons)
- Offer automatic and manual modes (preview results in an overlay, then execute)
- Manage users, tokens, files, and personal instructions via a clean dashboard

## Key features

- Browser extension (Manifest V3)
  - Content scripts analyze page text + HTML and call the backend
  - Runs actions: fillText, selectRadio, selectCheckbox, selectDropdown, click
  - Keyboard shortcuts and context menu integration
- Backend (FastAPI, async SQLAlchemy)
  - Three-agent pipeline: HTML parser → solution generator → action generator
  - RAG layer selects between direct file context or vector search across embeddings
  - Async form workflow: start, poll status, fetch actions
  - JWT cookie auth for web; API tokens for the extension
  - File uploads (images/PDFs), storage metadata, secure access
- Frontend (React + Vite)
  - Landing page, auth, dashboard
  - Manage API tokens, upload files, set personal instructions

## Architecture and data flow

1. **Browser extension collects page context**
    - Sends url, text, HTML, clipboard text, and optional screenshots to the backend (`POST /api/form/analyze/async`)

1. **Backend orchestrates a three-agent cascade**
    - **Step 1 – Parser Agent (Gemini 2.5 Flash/Pro):** extracts form questions with selectors, labels, hints, and metadata
    - **Step 2 – Solution Generator Agent:** produces natural-language answers per question, enriched with RAG context when available
    - **Step 3 – Action Generator Agent:** converts question/solution pairs into executable browser actions (fill/select/click)
    - Quality profiles (`fast`, `fast-pro`, `exact`, `exact-pro`) choose Flash vs. Pro variants per step

1. **Client polls and executes**
    - Background workflow persists status (`processing_step_1/2/3`) and generated actions in the database
    - Extension polls status and fetches final actions before executing them in the page (`addon/content/actions.js`)

## Repository structure

- addon/ — Browser extension (Manifest V3)
  - background-unified.js — background/service worker
  - content/ — content scripts (content.js + actions.js)
  - popup/ — popup UI
  - styles/ — overlay and content styles
  - utils/ — small helpers
  - manifest.json — extension metadata and permissions
  - README.md — in-depth extension docs (request/response formats, action types, troubleshooting)

- backend/ — FastAPI application
  - docker-compose.yml, Dockerfile, run.sh
  - requirements.txt — Python dependencies
  - src/
    - main.py — FastAPI app entrypoint (root_path=/api, CORS, sessions)
    - api/routers — auth, users, api-tokens, files, form (async workflow)
    - agents/ — HtmlFormParserAgent, SolutionGeneratorAgent, ActionGeneratorAgent, legacy FormValueGeneratorAgent
    - services/ — agent_service (three-step orchestration), rag_service (retrieval), document_processing_service, embedding_service
    - db/ — async engine, CRUD, models (users, files, document chunks, form requests/actions, tokens)
    - core/ — security (JWT cookies, OAuth), enums, lifespan
    - config/ — settings via environment variables

- frontend/ — React + Vite web app
  - src/pages — Home (landing), Login, Register, Dashboard
  - src/context — auth state
  - src/api — Axios base + typed API clients (auth, tokens, files)
  - vite.config.js, eslint.config.js

## Tech stack

- Frontend
  - React 19, Vite 7, React Router v7
  - Tailwind CSS (via @tailwindcss/vite), ESLint
  - Axios for API client with cookie-aware refresh handling

- Backend
  - FastAPI, Uvicorn
  - SQLAlchemy (async) with aiomysql (MySQL/MariaDB) by default; psycopg2-binary also included
  - Authlib (OAuth), python-jose (JWT), passlib[bcrypt]
  - PyMuPDF, Pillow, pytesseract for document parsing, OCR, and image preprocessing
  - google-adk session service with Gemini 2.5 Flash/Pro models for agents
  - ChromaDB HTTP server + Google `models/text-embedding-004` for vector search

- Addon (browser extension)
  - Manifest V3, content scripts, background worker, options and popup UI

## Security and privacy

- Authentication
  - Web app: JWT stored in an HttpOnly cookie named __session (configurable SameSite, Secure)
  - Extension: API tokens (`easyform_<128-hex>`) in `Authorization: Bearer <token>`
  - Access level checks enforced server-side

- Data handling
  - CORS is open by default to support extension use; deploy behind HTTPS only
  - Extension requires <all_urls> to analyze/fill forms; use manual mode on untrusted sites
  - Backend receives page content (text and HTML) for analysis. Ensure you comply with site policies and privacy laws

- Secrets and configuration
  - SECRET_KEY and SESSION_SECRET_KEY are required
  - SameSite policy validated, Secure cookie toggled via env
  - OAuth credentials optional (Google/GitHub/Discord supported by the codebase)

## Quality modes (agents)

- `fast`, `fast-pro`, `exact`, `exact-pro` — select Gemini Flash vs. Pro for each agent stage
- Internal batching keeps parser/solution/action throughput high while respecting rate limits

## Google ADK tool calling

- Agents are implemented with Google’s Agent Development Kit using `google.adk.agents.LlmAgent`, `Runner`, and an `InMemorySessionService` (see `backend/src/agents/**`).
- `backend/src/agents/agent.py` streams ADK events via `runner.run_async`, handling tool-calling outcomes like final responses and escalations while supporting automatic retries.
- Structured agents (parser and action generator) declare Pydantic schemas so ADK validates JSON tool outputs before the rest of the pipeline consumes them.
- Multi-modal requests leverage ADK’s tool-calling format by attaching PDFs, images, and screenshots through `types.Part.from_bytes` in `backend/src/agents/utils.py#create_multipart_query`.
- To add custom tools, register them on the ADK agent definition and extend the event loop in `StandardAgent`/`StructuredAgent` to dispatch `event.actions.tool_calls` as needed.

## Retrieval-augmented context

- **Direct context vs. RAG:** Files below configurable thresholds (≤5 files, ≤50 k characters, ≤10 PDF pages) are streamed directly into prompts. Larger datasets trigger RAG retrieval instead.
- **Vector store:** Document chunks are embedded with Google `models/text-embedding-004` (768-dim) and stored in a ChromaDB collection (`cosine` metric) per user.
- **Query building:** The backend synthesizes a search query from detected question titles/descriptions, retrieving top text and image chunks which feed the solution generator.
- **Screenshots:** Browser screenshots never enter the vector store; they are passed straight to the current analysis request.

## Document processing & OCR

- **PDFs:** Parsed via PyMuPDF; per-page text is chunked with overlap, images are extracted and OCR’d.
- **Images:** Standalone uploads run through Tesseract OCR; images are resized to 1024×1024 (max) before embedding.
- **Chunk metadata:** Each chunk stores page numbers, indices, and original formats to keep traceability in both the DB and vector store.
- **Fallbacks:** When OCR yields no text, a neutral placeholder still keeps the image discoverable in the shared embedding space.

## Browser extension specifics

- Permissions: activeTab, tabs, scripting, contextMenus, storage, clipboardRead, host_permissions: <all_urls>
- Commands in manifest
  - analyze-page — default: Ctrl+F (Windows/Linux), Command+F (macOS)
  - toggle-overlay — default: Ctrl+O (Windows/Linux), Command+O (macOS)
- You can customize shortcuts in your browser’s extension shortcuts settings
- See addon/README.md for request/response contracts and action types

## Getting started

Prerequisites:

- Node.js 18+ and npm for the frontend
- Python 3.12 for the backend
- A running MySQL/MariaDB (or set DATABASE_URL)

1. Backend

Environment variables (minimum):

- SECRET_KEY, SESSION_SECRET_KEY
- DATABASE_URL or DB_HOST, DB_USER, DB_PASSWORD, DB_NAME (defaults to mysql+aiomysql URL when DATABASE_URL is not provided)
- Optional: FRONTEND_BASE_URL, GOOGLE_CLIENT_ID/SECRET, and redirect URIs for OAuth

Development (Windows Git Bash):

```bash
cd backend
./run.sh u
```

This creates a venv, installs requirements, and starts Uvicorn on port 8080 (reload enabled by default). API base path is /api.

Docker (optional):

```bash
cd backend
docker compose up -d
```

This publishes the backend on localhost:7109 by default and uses WORKERS=1. Provide an .env file for secrets.

1. Frontend

```bash
cd frontend
npm install
# If backend runs on a different origin, create .env and set VITE_API_URL (e.g., http://localhost:8080/api or http://localhost:7109/api for docker)
npm run dev
```

1. Browser extension

- Chrome/Edge: chrome://extensions → Enable Developer Mode → Load unpacked → select addon/
- Firefox: about:debugging#/runtime/this-firefox → Load Temporary Add-on → select addon/manifest.json

Set the backend URL in the extension options or popup to your running base: e.g. <https://your-host/api> (the extension’s internal code calls the form endpoints underneath).

## Landing page (frontend)

The Home page explains the workflow and offers a streamlined CTA. Once authenticated, the Dashboard lets you:

- Create/delete API tokens for the extension
- Upload files (PNG, JPEG, GIF, WEBP, PDF – max 200MB)
- Set personal instructions to be included during AI analysis

## Notes on selectors and actions (addon)

- The backend returns a list of actions with selectors. The extension executes them with standard DOM APIs
- Action types: fillText, selectRadio, selectCheckbox, selectDropdown, click
- CSS selectors should be unique and stable; prefer name, then id, then a structural selector

## Troubleshooting

- Backend unreachable: verify VITE_API_URL (frontend) and extension settings; check backend logs; ensure HTTPS in production
- Auth and refresh: backend sets HttpOnly cookies; frontend’s Axios client will auto-refresh on 401 from protected calls
- Extension permissions: make sure the site is allowed; some browser-internal pages are not accessible

## Roadmap ideas

- Visual highlighting during action execution
- Dry-run/preview mode in overlay
- Action history and replay
- Multiple backend profiles; export/import configuration

## License

See LICENSE in the repository root.

## Acknowledgements

- Built with FastAPI, React, and Manifest V3
- AI flows powered via google-adk sessions and Gemini model families

