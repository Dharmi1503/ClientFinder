# ClientFinder

ClientFinder is an AI-assisted B2B lead generation system for discovering, filtering, enriching, scoring, and tracking outbound sales leads.

It combines:
- a FastAPI backend for scraping, enrichment, scoring, review workflows, and lead APIs
- a React + Vite frontend in `frontend2/` for the dashboard UI
- SQLite storage for leads, scraper health, and follow-up workflows

## What It Does

ClientFinder is built to help identify businesses that may need services like AI automation, website development, or other B2B offerings.

Typical flow:
- scrape leads from public sources
- validate and deduplicate results
- detect business pain/opportunity signals
- enrich leads with contact and company details
- score leads using AI-assisted logic
- save leads for review, status tracking, and follow-up

## Main Sources

The backend includes scrapers and source integrations such as:
- JustDial
- Google Maps
- Clutch
- Sulekha
- IndiaMART
- Instagram
- Facebook Pages
- Freelancer
- Reddit
- TradeIndia
- Truelancer
- Internshala

## Tech Stack

- Backend: Python, FastAPI, Pydantic
- Frontend: React, Vite, Tailwind CSS
- Database: SQLite
- HTTP / scraping utilities: `httpx`, `beautifulsoup4`, `ddgs`

## Project Structure

```text
backend/
  app/
    main.py              FastAPI routes
    pipeline.py          Lead generation pipeline
    database.py          SQLite schema and DB access
    ai.py                Scoring / AI logic
    enricher.py          Lead enrichment
    pain_signals.py      Opportunity / issue detection
    scrapers/            Source scrapers
    utils/               Validation, dedup, feedback helpers
  data/                  SQLite runtime data
  requirements.txt

frontend/                Older static frontend files
frontend2/               Current React + Vite frontend
scripts/                 Utility scripts
```

## Backend Setup

From the project root:

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run the backend:

```powershell
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 7000 --reload
```

API health check:

```text
GET http://localhost:7000/api/health
```

## Frontend Setup

The main frontend is in `frontend2/`.

```powershell
cd frontend2
npm install
npm run dev
```

Typical Vite local URL:

```text
http://localhost:5173
```

To build production assets:

```powershell
cd frontend2
npm run build
```

## Important API Routes

- `POST /api/find-clients`
- `POST /api/find-clients/intent`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/leads`
- `PUT /api/leads/{lead_id}/status`
- `PUT /api/leads/{lead_id}/followup`
- `PATCH /api/leads/{lead_id}/review`
- `GET /api/leads/followup-today`
- `GET /api/calibration`
- `GET /api/scrapers/health`
- `GET /api/sources/quality`
- `GET /api/llm/health`

## Environment Notes

This repo uses a local `.env` file that is intentionally ignored by Git.

If you are setting up the project on a new machine, create a `.env` file in the project root and add the keys your backend expects.

## Current Status

The repo is functional and now version-controlled on GitHub, but there are still some product and pipeline quality improvements worth doing next:
- tighten industry matching for niche searches
- reduce noisy-source scraping work
- improve pain-signal accuracy when search results are unavailable
- make scraper health metrics reflect true saved outcomes

## Git Workflow

Typical workflow after making changes:

```powershell
git status
git add .
git commit -m "Describe the change"
git push
```

## Notes

- `frontend/` appears to be an older UI version.
- `frontend2/` is the main modern dashboard app.
- SQLite database files, virtual environments, `node_modules`, and build output are ignored via `.gitignore`.
