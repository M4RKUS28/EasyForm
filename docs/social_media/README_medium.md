# EasyForm: Automating Web Forms with AI Agents on Cloud Run

*Published for participation in the Google Cloud Run Hackathon*

EasyForm is my experiment in turning repetitive paperwork into something an AI co-pilot can handle. The project marries a React dashboard, a Manifest V3 browser extension, and a FastAPI backend that I deploy on Cloud Run so the entire pipeline scales elastically while staying self-hosted.

## Why I Built It

Everyone knows the pain of onboarding portals, government PDFs, and vendor questionnaires. I wanted a system that could:

1. Understand arbitrary webpages
2. Pull in my personal documents (CVs, invoices, onboarding packs)
3. Generate precise answers
4. Replay those answers in the browser safely

## Architecture in a Nutshell

- **Browser Extension (Manifest V3)** collects HTML, visible text, clipboard snippets, and even screenshots from the active tab. It sends everything to the backend (`POST /api/form/analyze/async`).
- **Cloud Run Backend (FastAPI)** hosts a three-agent cascade powered by Gemini 2.5 Flash/Pro via google-adk:
  1. Parser Agent extracts question metadata and DOM selectors.
  2. Solution Generator Agent writes natural language answers, enriched through a Retrieval-Augmented Generation layer (Chroma + Google `gemini-embedding-001`).
  3. Action Generator Agent turns answers into executable “fill/select/click” steps.
- **React Dashboard** lets me upload files, manage API tokens, and monitor form runs. All assets live in Cloud Storage and are indexed for retrieval.

Running everything on Cloud Run means each asynchronous form workflow can scale independently while sharing the same codebase. The extension simply polls for status updates (`processing_step_1/2/3`) until actions are ready, then replays them inside the page.

## What Works Today

- Auto-detection of form inputs, labels, hints, and validation states.
- Context-aware answers using PDFs, images, clipboard text, or previously uploaded files.
- Safe execution plan with manual review mode in the extension overlay.
- JWT-secured dashboard + API tokens for the addon.

## Roadmap

- Batch processing for HR/fintech onboarding portals.
- Deeper document understanding (table extraction, handwritten OCR).
- Shared workspaces so teams can pool instructions and documents.

If you want to try the project or contribute, the repo is on GitHub and the landing page lives at [https://easyform-ai.com](https://easyform-ai.com).

