# Project Handover

## Repo

`C:\Users\utsav\Documents\Broader AI\Client finder\version2`

## What This Project Is

This is a Python FastAPI project for AI-assisted B2B lead generation for Broader AI.

Its purpose is to:

1. Scrape businesses from multiple public sources.
2. Filter and deduplicate leads.
3. Detect pain/opportunity signals like bad reviews, no Maps presence, outdated website, inactive social.
4. Enrich leads with website, email, phone, decision-maker, company size, and other signals.
5. Score leads using an LLM plus deterministic scoring rules.
6. Generate outreach messages for the best leads.
7. Save leads into a SQLite database for review and follow-up.

## Main Flow

Primary orchestrator:

- `app/pipeline.py`

Typical flow inside the pipeline:

1. Scrape from sources:
   - JustDial
   - Google Maps
   - Clutch
   - Sulekha
   - IndiaMART
   - Instagram
   - Facebook
   - Freelancer
   - Reddit
2. Drop noisy sources later in the pipeline.
3. Run business qualifier / source intent tagging.
4. Prefilter invalid leads.
5. Run pain signal detection.
6. Validate and deduplicate again.
7. Enrich lead data.
8. Apply contact gate.
9. Score leads.
10. Generate outreach for HOT leads.
11. Save to SQLite.

## Key Files

- `app/pipeline.py`: end-to-end pipeline orchestration
- `app/main.py`: FastAPI API routes
- `app/utils/validator.py`: lead filtering / validation
- `app/pain_signals.py`: review/site/social pain signal checks
- `app/enricher.py`: website/contact enrichment
- `app/ai.py`: LLM scoring and deterministic fallback logic
- `app/database.py`: SQLite schema, saving, querying, scraper health logging
- `app/filters/business_qualifier.py`: source-specific filtering and intent tagging
- `test_new_leads.py`: local test script to run pipeline manually

## Current Real Problem

The project is not mainly failing because of one crash. The main issue is lead quality and signal quality.

The pipeline runs, but:

1. Irrelevant leads can pass validation.
2. Noisy sources still run even though their outputs are later discarded.
3. Pain-signal checks can turn search/network failures into fake negative business signals.
4. Scraper health metrics are misleading.

## Exact Problems Found

### 1. Industry filtering fails open for many industries

File:

- `app/utils/validator.py`

Problem:

- `_INDUSTRY_KEYWORDS` only contains a few industries such as restaurants, hospitals, salons, etc.
- If the requested industry is not in that map, `_matches_target_industry()` returns `True`.
- That means a search like `interior design` is not properly constrained and unrelated businesses can pass.

Impact:

- Final leads may be valid businesses, but not valid businesses for the requested niche.

### 2. Freelancer and Reddit still run even though they are treated as noisy

File:

- `app/pipeline.py`

Problem:

- `scrape_freelancer(...)` and `scrape_reddit(...)` are still executed in the main scrape stage.
- Later, those leads are dropped using a noisy-source filter.

Impact:

- Wasted runtime
- Extra error logs
- Extra DDG/API noise
- No benefit to final lead output

### 3. Pain signals treat “no search result” like real business weakness

File:

- `app/pain_signals.py`

Problem:

- If DDG/Yahoo lookup fails or returns empty results, the code often ends up setting:
  - `no_google_maps_listing = True`
  - `last_social_post_old = True`
- That is not the same as verified absence. It often just means lookup failure.

Impact:

- Leads can get false negative pain signals.
- AI scoring may rate leads based on unreliable pain evidence.

### 4. Scraper health logging is overly optimistic

Files:

- `app/pipeline.py`
- `app/database.py`

Problem:

- scraper runs are logged with `saved=attempted` before validation, dedup, enrichment, and actual DB save happen.

Impact:

- Source health metrics do not reflect true source quality.
- Monitoring is misleading.

### 5. `total_raw` is not truly raw anymore

File:

- `app/pipeline.py`

Problem:

- The returned `total_raw` is based on a lead list that has already been filtered.

Impact:

- Harder to reason about funnel quality and stage-by-stage loss.

## Current State Of Improvements Already Made

These improvements were already introduced in the working tree:

1. Noisy source outputs from `freelancer` and `reddit` are dropped before downstream stages.
2. A prefilter step now removes many invalid leads before pain-signal detection.
3. Validator rules were tightened for directory/article/SEO-style fake business names.
4. `test_new_leads.py` was updated to match the current `run_pipeline(...)` function and current DB schema.

## What Should Be Fixed Next

Recommended fix order:

1. Remove `freelancer` and `reddit` from the actual scrape `gather(...)` call in `app/pipeline.py`.
2. Improve `app/utils/validator.py` industry matching:
   - add `interior design`
   - add more industry maps
   - or implement a safer fallback matcher for unknown industries
3. Change `app/pain_signals.py` so search failures are treated as `unknown`, not as negative business proof.
4. Fix scraper health logging so it reflects validated/saved outcomes instead of optimistic attempted counts.
5. Clarify funnel metrics:
   - `total_scraped_raw`
   - `total_after_prefilter`
   - `total_after_dedup`
   - `total_saved`

## If Another AI Should Work On This

Tell it to focus on these files first:

1. `app/pipeline.py`
2. `app/utils/validator.py`
3. `app/pain_signals.py`
4. `app/database.py`

Useful prompt for another AI:

```text
This repo is a FastAPI + SQLite lead-generation system.

Main issue: the pipeline runs, but lead quality is inconsistent.

Please inspect:
- app/pipeline.py
- app/utils/validator.py
- app/pain_signals.py
- app/database.py

Known problems:
1. freelancer and reddit are still scraped even though their outputs are later dropped as noisy
2. industry filtering fails open for industries not present in _INDUSTRY_KEYWORDS, such as "interior design"
3. pain_signals converts search failures into fake negative signals like no_google_maps_listing and last_social_post_old
4. scraper health logging uses optimistic values and does not reflect actual validated/saved leads
5. total_raw in the response is not truly raw anymore

Goal:
- improve final lead quality
- reduce false pain signals
- reduce wasted scrape work
- make monitoring/metrics trustworthy
```

## Short Summary

This project is an AI-powered business lead finder. It scrapes businesses, enriches them, scores them, and saves them.

The main problem is not that the app crashes. The main problem is that the pipeline still allows too much noisy or weakly relevant data through, and some of the “pain” evidence is based on unreliable search failures rather than verified business facts.
