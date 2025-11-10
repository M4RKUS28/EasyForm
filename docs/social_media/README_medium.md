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



## What Works Today

- Auto-detection of form inputs, labels, hints, and validation states.
- Context-aware answers using PDFs, images, clipboard text, or previously uploaded files.
- Safe execution plan with manual review mode in the extension overlay.
- JWT-secured dashboard + API tokens for the addon.

## Roadmap

- **Instantaneous Performance:** I want to optimize the entire AI pipeline, from analysis to execution, to make the process feel immediate. 
- **Near-Perfect Accuracy:** I plan to continue refining the RAG system and experiment with different prompting strategies to make the AI's answers even more reliable across a wider variety of forms.

If you want to try the project or contribute, the repo is on GitHub and the landing page lives at [https://easyform-ai.com](https://easyform-ai.com).

