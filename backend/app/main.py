"""
main.py
========
ClientFinder API - FastAPI app on port 7000
---------------------------------------------
Routes:
  POST /api/find-clients          -> Run full pipeline
  POST /api/find-clients/intent   -> Run intent-only pipeline
  GET  /api/leads                 -> Get all saved leads (with filters)
  PUT  /api/leads/{id}/status     -> Update pipeline status
  PUT  /api/leads/{id}/followup   -> Set follow-up date
  GET  /api/leads/followup-today  -> Due follow-ups for today
  GET  /api/health                -> Health check

Run with:
  uvicorn main:app --host 0.0.0.0 --port 7000 --reload
"""

import asyncio
import time
import uuid
import os
from datetime import date
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.database import (
    ensure_db,
    create_api_key,
    get_api_key,
    revoke_api_key,
    list_api_keys,
    get_all_leads,
    get_all_source_quality,
    get_followups_today,
    get_llm_health_summary,
    get_rejected_leads,
    get_review_queue,
    get_scraper_health,
    get_scraper_health_for_source,
    set_follow_up,
    update_review,
    update_status,
)
from app.pipeline import run_intent_pipeline, run_pipeline
from app.utils.feedback import get_adjusted_score_floors, get_calibration_data

# In-memory job store (persists while server is up)
_JOBS: dict[str, dict] = {}


app = FastAPI(
    title="ClientFinder - Broader AI",
    description="AI-powered B2B lead generation for Indian businesses",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    # Load environment (ADMIN_KEY) from .env if present
    try:
        load_dotenv()
    except Exception:
        pass
    ensure_db()
    print("[STARTUP] ClientFinder v2 ready on port 7000")


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------


def require_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> dict:
    """FastAPI dependency that verifies the provided X-API-Key header.

    On success returns the api_keys row as a dict. On failure raises 403.
    """
    if not x_api_key:
        raise HTTPException(status_code=403, detail="Missing API key")
    row = get_api_key(x_api_key)
    if not row:
        raise HTTPException(status_code=403, detail="Invalid API key")
    if not int(row.get("is_active", 0)):
        raise HTTPException(status_code=403, detail="API key revoked")
    return row


def require_admin(x_admin_key: str = Header(None, alias="X-Admin-Key")) -> None:
    """Require the admin key from environment to access admin endpoints."""
    admin_key = os.getenv("ADMIN_KEY")
    if not admin_key:
        raise HTTPException(status_code=403, detail="Admin access not configured")
    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


class FindClientsRequest(BaseModel):
    service: str = Field(
        ...,
        description="What you offer - e.g. 'AI automation for businesses'",
        examples=["AI automation and website development"],
    )
    industry: str = Field(
        ...,
        description="Target industry / keyword - e.g. 'hospitals', 'restaurants'",
        examples=["hospitals"],
    )
    location: str = Field(
        ...,
        description="Indian city to target",
        examples=["Delhi"],
    )
    budget_range: str = Field(
        default="Rs50k-Rs2L",
        description="Your typical deal size - used by AI for scoring",
        examples=["Rs50k-Rs2L"],
    )
    max_leads: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max leads in response",
    )
    fast_mode: bool = Field(
        default=True,
        description="Fast mode skips LinkedIn/News/IndiaMART enrichment. Faster but less data.",
    )


class StatusUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        description="New | Contacted | Replied | Meeting | Closed | Dead",
        examples=["Contacted"],
    )


class FollowUpRequest(BaseModel):
    follow_up_date: str = Field(
        ...,
        description="Follow-up date in YYYY-MM-DD format",
        examples=["2026-04-10"],
    )
    notes: str = Field(
        default="",
        description="Optional note to attach",
    )


class ReviewUpdateRequest(BaseModel):
    action: str = Field(
        ...,
        description="approved or rejected",
        examples=["approved"],
    )
    note: str = Field(
        default="",
        description="Optional reviewer note",
    )


class AdminCreateKeyRequest(BaseModel):
    name: str = Field(..., description="Name for the API key (e.g. username)")


# ---------------------------------------------------------------------------
# Admin endpoints (protected by ADMIN_KEY env var via X-Admin-Key header)
# ---------------------------------------------------------------------------


@app.post("/admin/keys")
async def admin_create_key(body: AdminCreateKeyRequest, _admin: None = Depends(require_admin)):
    """Create a new API key for a user. Returns the generated key string."""
    key = create_api_key(body.name, created_by="admin")
    return {"key": key}


@app.delete("/admin/keys/{key}")
async def admin_revoke_key(key: str, _admin: None = Depends(require_admin)):
    """Revoke (deactivate) an API key. Returns 200 if successful."""
    ok = revoke_api_key(key)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found or already revoked")
    return {"ok": True}


@app.get("/admin/keys")
async def admin_list_keys(_admin: None = Depends(require_admin)):
    """List stored API keys with metadata: name, created_by, created_at, is_active."""
    rows = list_api_keys()
    result = [
        {
            "name": r.get("name"),
            "created_by": r.get("created_by"),
            "created_at": r.get("created_at"),
            "is_active": bool(r.get("is_active")),
        }
        for r in rows
    ]
    return {"count": len(result), "keys": result}


@app.get("/api/health")
async def health(api_key: dict = Depends(require_api_key)):
    """Quick health check that confirms the API is up."""
    return {
        "status": "ok",
        "service": "ClientFinder",
        "version": "2.0.0",
        "date": date.today().isoformat(),
    }


@app.get("/api/calibration")
async def get_calibration(api_key: dict = Depends(require_api_key)):
    """
    Returns real-deal close rates by source and industry, plus
    current score floor adjustments derived from closed leads.

    Also includes a disclaimer about speed_to_close being an LLM estimate
    until at least 10 real outcomes are logged.

    This endpoint powers the feedback loop - as you mark leads
    Closed or Dead, this data improves automatically.
    """
    cal = get_calibration_data()
    floors = get_adjusted_score_floors()

    return {
        "calibration": cal,
        "score_adjustments": floors,
        "speed_to_close_warning": (
            "speed_to_close_estimate is generated by the LLM based on industry norms. "
            "It is NOT based on your actual closed deals and should not be trusted "
            f"until at least 10 outcomes are logged (currently: {cal['total_outcomes']})."
        ),
        "how_to_improve": (
            "Mark leads as Closed or Dead via PUT /api/leads/{id}/status. "
            "Each outcome is logged and improves scoring accuracy over time."
        ),
    }


@app.post("/api/find-clients")
async def find_clients(request: FindClientsRequest, background_tasks: BackgroundTasks, api_key: dict = Depends(require_api_key)):
    """
    Start the lead generation pipeline as a background job.

    Returns immediately with a job_id.
    Poll GET /api/jobs/{job_id} to check progress and get results.

    Use fast_mode=true (default) for quick results (~30-60s).
    Use fast_mode=false for deep enrichment with LinkedIn/News/IndiaMART (~3-5min).
    """
    job_id = str(uuid.uuid4())[:8]

    _JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "stage": "queued",
        "message": "Pipeline queued...",
        "started_at": time.strftime("%H:%M:%S"),
        "request": request.model_dump(),
        "result": None,
        "error": None,
    }

    def _progress(stage: str, message: str):
        _JOBS[job_id]["stage"] = stage
        _JOBS[job_id]["message"] = message

    async def _run():
        try:
            directory_result, intent_result = await asyncio.gather(
                run_pipeline(
                    service=request.service,
                    city=request.location,
                    industry=request.industry,
                    budget_range=request.budget_range,
                    max_leads=request.max_leads,
                    fast_mode=request.fast_mode,
                    on_progress=_progress,
                ),
                run_intent_pipeline(
                    service=request.service,
                    city=request.location,
                    industry=request.industry,
                    budget_range=request.budget_range,
                    max_leads=request.max_leads,
                    on_progress=_progress,
                ),
            )
            result = {
                "directory_pipeline": directory_result,
                "intent_pipeline": intent_result,
                "total_saved": directory_result.get("total_saved", 0)
                + intent_result.get("total_saved", 0),
                "hot": directory_result.get("hot", 0) + intent_result.get("hot", 0),
                "warm": directory_result.get("warm", 0) + intent_result.get("warm", 0),
                "cold": directory_result.get("cold", 0) + intent_result.get("cold", 0),
                "scrape_date": date.today().isoformat(),
            }
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["stage"] = "done"
            _JOBS[job_id]["message"] = (
                f"Complete - {result.get('hot', 0)} HOT, "
                f"{result.get('warm', 0)} WARM leads found."
            )
            _JOBS[job_id]["result"] = result
        except Exception as exc:
            print(f"[JOB {job_id}] error: {exc}")
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["stage"] = "error"
            _JOBS[job_id]["message"] = str(exc)
            _JOBS[job_id]["error"] = str(exc)

    background_tasks.add_task(_run)

    return {
        "job_id": job_id,
        "status": "running",
        "message": "Pipeline started. Poll GET /api/jobs/{job_id} for results.",
        "poll_url": f"/api/jobs/{job_id}",
    }


@app.post("/api/find-clients/intent")
async def find_clients_intent(request: Request, background_tasks: BackgroundTasks, api_key: dict = Depends(require_api_key)):
    """
    Start the intent pipeline only.
    Scrapes Freelancer + Reddit for active buyer signals.
    """
    body = await request.json()

    service = body.get("service", "")
    industry = body.get("industry", "")
    location = body.get("location", body.get("city", ""))
    budget_range = body.get("budget_range", "Rs50k-Rs2L")
    max_leads = int(body.get("max_leads", 20))

    if not service or not industry or not location:
        return JSONResponse(
            status_code=422,
            content={"error": "service, industry, and location are required"},
        )

    job_id = str(uuid.uuid4())[:8]
    _JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "stage": "intent_scraping",
        "message": "Starting intent pipeline...",
        "started_at": time.strftime("%H:%M:%S"),
        "request": {
            "service": service,
            "industry": industry,
            "location": location,
            "budget_range": budget_range,
            "max_leads": max_leads,
        },
        "result": None,
        "error": None,
    }

    async def run_intent_job():
        def on_progress(stage: str, message: str):
            _JOBS[job_id]["stage"] = stage
            _JOBS[job_id]["message"] = message

        try:
            result = await run_intent_pipeline(
                service=service,
                city=location,
                industry=industry,
                budget_range=budget_range,
                max_leads=max_leads,
                on_progress=on_progress,
            )
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["stage"] = "done"
            _JOBS[job_id]["result"] = result
            _JOBS[job_id]["message"] = (
                f"Done! HOT={result.get('hot', 0)} "
                f"WARM={result.get('warm', 0)} "
                f"COLD={result.get('cold', 0)}"
            )
        except Exception as exc:
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["stage"] = "error"
            _JOBS[job_id]["error"] = str(exc)
            _JOBS[job_id]["message"] = str(exc)
            print(f"[INTENT JOB ERROR] {exc}")

    background_tasks.add_task(run_intent_job)

    return {
        "job_id": job_id,
        "status": "running",
        "poll_url": f"/api/jobs/{job_id}",
    }


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, api_key: dict = Depends(require_api_key)):
    """
    Poll for pipeline results.

    status = 'running' -> still working, check again in 10s
    status = 'done'    -> results ready in 'result' field
    status = 'error'   -> something failed, check 'error' field
    """
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@app.get("/api/jobs")
async def list_jobs(api_key: dict = Depends(require_api_key)):
    """List all pipeline jobs started this session."""
    return [{k: v for k, v in job.items() if k != "result"} for job in _JOBS.values()]


@app.get("/scrapers/health")
@app.get("/api/scrapers/health", include_in_schema=False)
async def scraper_health(api_key: dict = Depends(require_api_key)):
    """Return the latest run stats for all scraper sources."""
    rows = get_scraper_health()
    return {
        "count": len(rows),
        "sources": rows,
    }


@app.get("/scrapers/health/{source}")
@app.get("/api/scrapers/health/{source}", include_in_schema=False)
async def scraper_health_by_source(source: str, api_key: dict = Depends(require_api_key)):
    """Return the last 10 runs for a specific scraper source."""
    rows = get_scraper_health_for_source(source, limit=10)
    return {
        "source": source,
        "count": len(rows),
        "runs": rows,
    }


@app.get("/sources/quality")
@app.get("/api/sources/quality", include_in_schema=False)
async def sources_quality(api_key: dict = Depends(require_api_key)):
    """Return source quality and weight for all sources, worst first."""
    rows = get_all_source_quality()
    return {
        "count": len(rows),
        "sources": rows,
    }


@app.get("/llm/health")
@app.get("/api/llm/health", include_in_schema=False)
async def llm_health(api_key: dict = Depends(require_api_key)):
    """Return tier usage, avg response time, and failure rate in the last 24 hours."""
    rows = get_llm_health_summary()
    return {
        "count": len(rows),
        "tiers": rows,
    }


@app.get("/api/leads")
async def get_leads(
    city: Optional[str] = Query(None, description="Filter by city name, case-insensitive"),
    category: Optional[str] = Query(
        None, description="Filter by business category/type, case-insensitive"
    ),
    label: Optional[str] = Query(None, description="Filter by lead label: HOT | WARM | COLD"),
    min_score: int = Query(0, ge=0, le=100, description="Minimum composite score"),
    max_score: int = Query(100, ge=0, le=100, description="Maximum composite score"),
    review_status: Optional[str] = Query(
        None, description="approved | pending_review | rejected"
    ),
    source: Optional[str] = Query(
        None, description="Lead source like justdial or google_maps"
    ),
    pipeline: Optional[str] = Query(
        None, description="Filter by pipeline type: main_pipeline | intent_pipeline"
    ),
    has_email: bool = Query(False, description="Only return leads that have an email"),
    has_phone: bool = Query(False, description="Only return leads that have a phone"),
    sort_by: str = Query("recent", description="recent | score | oldest"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    api_key: dict = Depends(require_api_key),
):
    """
    Fetch saved leads from the database with optional filters.

    Examples:
      GET /api/leads                 -> all leads
      GET /api/leads?source=justdial -> JustDial leads
      GET /api/leads?city=Mumbai     -> Mumbai leads
    """
    if min_score > max_score:
        raise HTTPException(status_code=422, detail="min_score cannot be greater than max_score")

    total, leads = get_all_leads(
        city=city,
        category=category,
        label=label,
        min_score=min_score,
        max_score=max_score,
        review_status=review_status,
        source=source,
        pipeline_type=pipeline,
        has_email=has_email,
        has_phone=has_phone,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": leads,
    }


@app.get("/api/leads/review-queue")
@app.get("/leads/review-queue", include_in_schema=False)
async def review_queue(
    limit: int = Query(200, ge=1, le=1000, description="Max rows to return"),
    api_key: dict = Depends(require_api_key),
):
    """Return all leads awaiting human review."""
    leads = get_review_queue(limit=limit)
    return {
        "count": len(leads),
        "review_status": "pending_review",
        "leads": leads,
    }


@app.get("/api/leads/rejected")
@app.get("/leads/rejected", include_in_schema=False)
async def rejected_leads(
    limit: int = Query(200, ge=1, le=1000, description="Max rows to return"),
    api_key: dict = Depends(require_api_key),
):
    """Return rejected leads and the reasons they failed input validation."""
    leads = get_rejected_leads(limit=limit)
    return {
        "count": len(leads),
        "leads": leads,
    }


@app.put("/api/leads/{lead_id}/status")
async def patch_status(lead_id: int, body: StatusUpdateRequest, api_key: dict = Depends(require_api_key)):
    """
    Update a lead's pipeline status.

    Valid values: New | Contacted | Replied | Meeting | Closed | Dead
    """
    try:
        update_status(lead_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": lead_id, "status": body.status, "ok": True}


@app.put("/api/leads/{lead_id}/followup")
async def patch_followup(lead_id: int, body: FollowUpRequest, api_key: dict = Depends(require_api_key)):
    """
    Set a follow-up date (YYYY-MM-DD) and optional note for a lead.
    Notes are appended - existing notes are not overwritten.
    """
    try:
        set_follow_up(lead_id, body.follow_up_date, body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "id": lead_id,
        "follow_up_date": body.follow_up_date,
        "ok": True,
    }


@app.patch("/api/leads/{lead_id}/review")
@app.patch("/leads/{lead_id}/review", include_in_schema=False)
async def patch_review(lead_id: int, body: ReviewUpdateRequest, api_key: dict = Depends(require_api_key)):
    """Approve or reject a lead after human review."""
    try:
        update_review(lead_id, body.action, body.note)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 422
        raise HTTPException(status_code=status_code, detail=detail)
    return {
        "id": lead_id,
        "review_status": body.action.lower(),
        "note": body.note,
        "ok": True,
    }


@app.get("/api/leads/followup-today")
async def followup_today(api_key: dict = Depends(require_api_key)):
    """
    Return all leads with a follow-up scheduled for today.
    Use this for your daily outreach routine.
    """
    leads = get_followups_today()
    return {
        "date": date.today().isoformat(),
        "count": len(leads),
        "leads": leads,
    }
