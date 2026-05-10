# ClientFinder Architecture Reference

## Overview

This repo is an AI-powered lead generation and scoring system for Indian B2B businesses.
It exposes a FastAPI backend in `app/main.py`, runs a multi-stage lead scraping and enrichment pipeline in `app/pipeline.py`, and stores results in SQLite via `app/database.py`.

The pipeline is designed to:
- scrape business listings from multiple sources,
- qualify and deduplicate leads,
- enrich leads with website/contact data,
- identify pain signals,
- score leads with LLM analysis,
- generate outreach messages for HOT leads,
- save leads to the DB,
- support review, follow-up, and health endpoints.

## High-Level Module Map

- `app/main.py`
  - FastAPI app with endpoints
  - background job orchestration for `/api/find-clients`
  - lead viewing, status/follow-up/review updates
  - health, scraper health, source quality, LLM health, calibration

- `app/pipeline.py`
  - full pipeline orchestrator (`run_pipeline()`)
  - stages 2–8 of lead processing
  - result building for API responses

- `app/scrapers/`
  - active scrapers: `justdial`, `google_maps`, `clutch`, `sulekha`, `indiamart_source`, `instagram_hashtag`, `facebook_pages`
  - disabled sources are present but not used

- `app/pain_signals.py`
  - non-LLM pain signal detection
  - Google review / maps / website / social / hiring signals

- `app/enricher.py`
  - website discovery and contact extraction
  - email/phone/domain extraction from pages and contact links

- `app/ai.py`
  - LLM scoring prompt engine
  - message fallback and 3-tier LLM chain
  - deterministic scoring and client readiness score

- `app/messages.py`
  - WhatsApp / LinkedIn / email message generation for HOT leads
  - uses pain templates or LLM-generated opener

- `app/database.py`
  - SQLite schema and persistence
  - lead save/upsert, filters, reviews, scraper logs, analytics
  - duplicate detection and review flagging

- `app/utils/`
  - `deduplicator.py`: batch DB duplicate filtering
  - `validator.py`: lead quality validation
  - `contact_gate.py`: zero-contact lead gating
  - `lead_input.py`: sanitization and strict DB validation
  - `feedback.py`: calibration and outcome logging

- `app/review_config.py`
  - review thresholds and noisy source constants

## API Endpoints

### Public / main workflow

- `GET /api/health`
  - returns service status and current date

- `POST /api/find-clients`
  - starts a background pipeline job
  - request body: `service`, `industry`, `location`, `budget_range`, `max_leads`, `fast_mode`
  - response: `job_id`, `status`, `poll_url`

- `GET /api/jobs/{job_id}`
  - polls pipeline progress and result
  - `status`: `running` / `done` / `error`
  - `message` and `error` explain state

- `GET /api/jobs`
  - lists all jobs in current server session

### Lead management

- `GET /api/leads`
  - filters by city, category, score range, review status, source, email/phone presence
  - returns paginated lead rows

- `PUT /api/leads/{lead_id}/status`
  - update lead pipeline status
  - valid statuses: `New`, `Contacted`, `Replied`, `Meeting`, `Closed`, `Dead`
  - `Closed` / `Dead` also trigger feedback logging

- `PUT /api/leads/{lead_id}/followup`
  - set follow-up date and note
  - date validated as `YYYY-MM-DD`

- `PATCH /api/leads/{lead_id}/review`
  - approve or reject human review
  - valid actions: `approved`, `rejected`
  - writes review log and updates source quality

- `GET /api/leads/followup-today`
  - returns leads due for follow-up today

- `GET /api/leads/review-queue`
  - returns pending-review leads

- `GET /api/leads/rejected`
  - returns rejected leads and reasons

### Diagnostics / analytics

- `GET /scrapers/health` or `/api/scrapers/health`
  - latest scraper run health stats

- `GET /scrapers/health/{source}`
  - recent runs for a single scraper source

- `GET /sources/quality` or `/api/sources/quality`
  - source quality metrics and weights

- `GET /llm/health` or `/api/llm/health`
  - tier usage, avg response time, failure rate

- `GET /api/calibration`
  - close rates by source and industry
  - score floor adjustments from feedback

## Pipeline Flow

The pipeline has eight major stages in `app/pipeline.py`.

```mermaid
flowchart TD
  A[POST /api/find-clients] --> B[Create job_id & enqueue background task]
  B --> C[run_pipeline(service, city, industry, budget_range, max_leads, fast_mode)]

  C --> S2[Stage 2: scrape sources in parallel]
  S2 --> S2A{Scraper result}
  S2A -->|list| S2B[append raw leads]
  S2A -->|exception| S2C[mark source failed]
  S2B --> S2D[assign source metadata]
  S2D --> S2E[log scraper attempt counts]
  S2E --> S2F[if no raw leads => return empty result]

  S2F --> S22[Stage 2.2: BusinessQualifier]
  S22 --> S23[Stage 2.5: prefilter + pain signals]
  S23 --> S3[Stage 3: validate + dedupe]

  S3 --> D1{validated leads exist?}
  D1 -->|no| R0[finalize logs + return empty result]
  D1 -->|yes| S4[Stage 4: enrich leads in batches]

  S4 --> S5[Stage 5: contact gate]
  S5 --> S6[Stage 6: AI scoring]
  S6 --> S6A{score_lead success?}
  S6A -->|yes| S6B[use LLM results]
  S6A -->|timeout/error| S6C[deterministic fallback scores]
  S6B --> S65[Stage 6.5: readiness score]
  S6C --> S65

  S65 --> S7[Stage 7: message generation for top HOT]
  S7 --> S8[Stage 8: save leads to DB]
  S8 --> T[Return success payload + job completes]

  subgraph sc[Scraper sources]
    JD[JustDial] -->|active| S2
    GM[Google Maps] -->|active| S2
    CL[Clutch] -->|active| S2
    SU[Sulekha] -->|active| S2
    IM[IndiaMART] -->|active| S2
    IG[Instagram] -->|active| S2
    FB[Facebook Pages] -->|active| S2
  end
```

## Detailed Stage Behavior

### Stage 2: Scrape sources

- Parallel scrapers are executed via `asyncio.gather(...)`.
- Any scraper exception is caught and logged.
- Each successful lead gets `source` assigned.
- If zero raw leads remain, pipeline returns immediately.

### Stage 2.2: Business Qualifier

- `app.filters.business_qualifier.tag_directory_leads()` tags each lead with source intent metadata.
- This metadata is used later by the AI scorer.

### Stage 2.5: Prefilter + pain signal detection

- `filter_valid_leads()` drops: invalid names, non-business directory pages, obvious property/listing pages, no contact info, city/industry mismatch.
- Then `batch_detect_pain_signals()` adds these fields:
  - `negative_reviews_found`
  - `no_google_maps_listing`
  - `website_is_outdated`
  - `website_not_mobile`
  - `last_social_post_old`
  - `hiring_manual_roles`
  - `has_physical_location`
  - `whatsapp_hint`

- Pain signals are used by AI scoring and message generation.

### Stage 3: Clean + deduplicate

- `filter_valid_leads()` runs again to remove any invalid lead after pain-signal metadata changes.
- `_deduplicate_within_batch()` keeps the strongest duplicate by company + city.
- `batch_filter_duplicates()` removes leads already in DB.

### Stage 4: Enrich

- `app.enricher.enrich_lead()` runs in batches of 10.
- This step finds website domain, scrapes pages, extracts email/phone/decision maker.
- `fast_mode=True` skips deeper or slower checks for speed.

### Stage 5: Contact gate

- `batch_apply_contact_gate()` ensures every actionable lead has at least one contact method.
- If a lead has zero contact methods after enrichment:
  - `contact_score` is set to `0`
  - `label` is forced to `COLD`
  - note is appended explaining the gate
  - lead remains in DB to avoid future re-scraping

### Stage 6: AI scoring

- Each actionable lead is scored by `app.ai.score_lead()`.
- The prompt includes lead details, contact availability, source signal, and context.
- The LLM returns full analyst output, including:
  - `fit_score`, `buying_intent_score`, `contactability_score`
  - `decision_maker`, `pain_point`, `buying_signals`
  - `objection_1`, `rebuttal_1`, `objection_2`, `rebuttal_2`
  - `best_channel`, `channel_reason`, `personalized_opener`
  - `speed_to_close`

- Results are normalized and mapped for storage.

#### Fallbacks and error handling

- If `score_lead()` times out after 90s or raises:
  - `_rule_based_scoring_fallback()` is used instead.
  - Warning is printed and scoring still continues.

### Stage 6.5: Client readiness score

- `compute_client_readiness_score()` computes a deterministic score from:
  - money signals
  - pain signals
  - reachability signals
- This score is informational and does not override HOT/WARM/COLD.

### Stage 7: Message generation

- Only top HOT leads are sent to message generation.
- `app.messages.generate_messages()` builds prompts for:
  - 3 WhatsApp variants
  - LinkedIn message
  - email subject + body
- If message generation times out, default fallback messages are used.

### Stage 8: Save to DB

- `app.database.save_lead()` sanitizes and validates every lead.
- If validation fails, the lead is rejected and stored in `rejected_leads`.
- Duplicate existing leads are updated instead of inserted.
- Review status is computed from composite score:
  - `< 20` → `rejected`
  - `< 60` → `pending_review`
  - otherwise `approved`
- Flags are added for low score, missing contact, or noisy source.

## Database & Review Logic

- `app/database.py` defines the SQLite schema and operations.
- `save_lead()` upserts by `company_name + city`.
- `update_status()` changes pipeline status and logs Closed/Dead outcomes via `app.utils.feedback.log_outcome()`.
- `set_follow_up()` validates date format and appends notes.
- `update_review()` approves/rejects and writes audit records.
- `get_all_leads()` supports filter queries used by `/api/leads`.
- `log_scraper_run()` persists scraper success/failure metrics.

## Error and Guard Conditions

### In `app/main.py`
- `POST /api/find-clients` catches exception in background task and sets job status to `error`.
- `GET /api/jobs/{job_id}` returns `404` if job not found.
- `GET /api/leads` rejects invalid score range if `min_score > max_score`.
- `PUT /api/leads/{lead_id}/status` validates status values.
- `PUT /api/leads/{lead_id}/followup` validates `YYYY-MM-DD`.
- `PATCH /api/leads/{lead_id}/review` validates review action and lead existence.

### In `app/pipeline.py`
- No raw leads → returns immediately with zero counts.
- Scraper exceptions are logged but do not crash the entire pipeline.
- Enrichment exceptions preserve the lead and continue.
- AI timeouts/errors trigger deterministic fallback.

### In `app/database.py`
- Invalid leads at save time are rejected and stored separately.
- Duplicate detection uses normalized company/city matching.
- Source quality recalculation happens after review updates.

## Key Interesting Behaviors

- `fast_mode` controls enrichment depth and is intended to speed up pipeline runs.
- The system keeps zero-contact leads in DB to avoid re-scraping them again.
- Human feedback from `Closed`/`Dead` outcomes is used to adjust future scoring.
- The final API response returns only top HOT leads plus top 5 WARM leads.
- Full lead details are still preserved in DB for review and future filtering.

## How the automation works

1. User calls `/api/find-clients`.
2. Server enqueues a background pipeline job and returns `job_id`.
3. Scrapers collect raw leads concurrently.
4. Leads are pre-filtered, tagged for intent, and pain signals are detected.
5. Clean leads are deduplicated against existing DB records.
6. Leads are enriched with website/contact information.
7. Leads without contact are gated and forced to `COLD`.
8. Actionable leads are scored by the LLM.
9. Top HOT leads receive outreach messages.
10. All processed leads are saved and the job result becomes available.

## Notes for Review

- The repo does not expose a frontend; it is a backend API service.
- `data/clientfinder.db` is the SQLite persistence store.
- `requirements.txt` defines Python dependencies for FastAPI, OpenAI client, ddgs, httpx, and others.
- `app/llm_config.py` defines a fallback ternary chain, but only Groq is actively configured in `app/ai.py`.

---

This reference is intended as a complete architecture guide for the current codebase.
