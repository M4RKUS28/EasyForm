# EasyForm

AI-powered form filling across the web. EasyForm combines a modern React frontend, a FastAPI backend with multi-agent form analysis, and a Manifest V3 browser extension that analyzes pages and fills forms automatically.

Visit the API docs after running the backend at /api/docs. Health check is at /api/health.

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
	- "Parser" agent extracts form structure (labels, selectors, types, options)
	- "Generator" agent produces values/actions per field
	- Async form workflow: start, poll status, fetch actions
	- JWT cookie auth for web; API tokens for the extension
	- File uploads (images/PDFs), storage metadata, secure access
- Frontend (React + Vite)
	- Landing page, auth, dashboard
	- Manage API tokens, upload files, set personal instructions

## Architecture and data flow

1) Browser extension collects page context
	 - Sends url, text, and HTML (and optionally screenshots) to the backend: POST /api/form/analyze/async

2) Backend orchestrates multi-step AI analysis
	 - Step 1: HTML Form Parser Agent extracts structured fields with selectors and labels
	 - Step 2: Form Value Generator Agent returns an actions list (fill/select/click)
	 - Quality modes: fast, medium, exact, and the corresponding “-ultra” variants (ultra processes field groups in parallel)

3) Client polls and executes
	 - Poll /api/form/request/{id}/status
	 - When completed, GET /api/form/request/{id}/actions returns actions
	 - Extension executes actions against the DOM (content/actions.js)

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
		- agents/ — HtmlFormParserAgent, FormValueGeneratorAgent, and instructions
		- services/ — agent_service (quality modes, batching, ultra concurrency), others
		- db/ — async engine, CRUD, models (users, files, form requests/actions, tokens)
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
	- BeautifulSoup4 + lxml, PyPDF2, Pillow for data extraction
	- google-adk for agent sessions; Gemini models referenced in agent flows

- Addon (browser extension)
	- Manifest V3, content scripts, background worker, options and popup UI

## Security and privacy

- Authentication
	- Web app: JWT stored in an HttpOnly cookie named __session (configurable SameSite, Secure)
	- Extension: API tokens (easyform_<128-hex>) in Authorization: Bearer <token>
	- Access level checks enforced server-side

- Data handling
	- CORS is open by default to support extension use; deploy behind HTTPS only
	- Extension requires <all_urls> to analyze/fill forms; use manual mode on untrusted sites
	- Backend receives page content (text and HTML) for analysis. Ensure you comply with site policies and privacy laws

- Secrets and configuration
	- SECRET_KEY and SESSION_SECRET_KEY are required
	- SameSite policy validated, Secure cookie toggled via env
	- OAuth credentials optional (Google/GitHub/Discord supported by the codebase)

## API overview (high level)

- Auth (/api/auth)
	- POST /login (form-encoded): returns success and sets cookies
	- POST /logout
	- POST /refresh (cookie-protected)
	- POST /signup
	- OAuth flows for Google/GitHub/Discord

- Users (/api/users)
	- GET /me — current session’s user or null
	- PUT /{user_id} — update (role/access checks apply)
	- PUT /{user_id}/change_password
	- DELETE /me, DELETE /{user_id}

- API Tokens (/api/api-tokens)
	- POST / — create token (only returned once)
	- GET / — list tokens
	- DELETE /{token_id}

- Files (/api/files)
	- POST /upload — base64 file upload (images/PDFs)
	- GET / — list files for current user
	- GET /{file_id} — download as base64
	- DELETE /{file_id}

- Form (/api/form)
	- POST /analyze/async — start analysis, returns request_id
	- GET /request/{request_id}/status — poll status
	- GET /request/{request_id}/actions — get actions when completed
	- DELETE /request/{request_id} — cancel/delete

All endpoints are prefixed by /api. See /api/docs for interactive documentation.

## Quality modes (agents)

- fast, medium, exact — choose underlying Gemini model per step
- -ultra variants — process field groups concurrently (up to 10), faster on large forms

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

1) Backend

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

2) Frontend

```bash
cd frontend
npm install
# If backend runs on a different origin, create .env and set VITE_API_URL (e.g., http://localhost:8080/api or http://localhost:7109/api for docker)
npm run dev
```

3) Browser extension

- Chrome/Edge: chrome://extensions → Enable Developer Mode → Load unpacked → select addon/
- Firefox: about:debugging#/runtime/this-firefox → Load Temporary Add-on → select addon/manifest.json

Set the backend URL in the extension options or popup to your running base: e.g. https://your-host/api (the extension’s internal code calls the form endpoints underneath).

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

