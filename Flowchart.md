# ClientFinder Flowchart

This file maps the full repository architecture and shows how code files communicate with each other.
The diagram is based on real imports and runtime flow for the main API and lead pipeline.

## How to read this chart

- Each box is a code file or endpoint.
- Arrows show who calls whom and what moves between files.
- Groups are logical layers: API, pipeline, scrapers, enrichment, database.
- The flow starts from `app/main.py` API calls and moves through `app/pipeline.py`.

## Detailed Mermaid flowchart

```mermaid
flowchart LR
    subgraph API[API layer in app/main.py]
        M1[POST /api/find-clients]\n(start pipeline job)
        M2[GET /api/jobs/{job_id}]\n(poll job status)
        M3[GET /api/leads]\n(fetch saved leads)
        M4[PUT /api/leads/{id}/status]\n(update lead status)
        M5[PUT /api/leads/{id}/followup]\n(set follow-up)
        M6[PATCH /api/leads/{id}/review]\n(approve/reject review)
        M7[GET /api/calibration]\n(score calibration)
        M8[GET /scrapers/health]\n(scraper health stats)
        M9[GET /llm/health]\n(LLM health stats)
    end

    subgraph PIPE[Pipeline engine in app/pipeline.py]
        P1[run_pipeline()]\n(main orchestrator)
        P2[tag_directory_leads()]\n(source intent tagging)
        P3[filter_valid_leads()]\n(initial validation)
        P4[batch_detect_pain_signals()]\n(pain signal tags)
        P5[enrich_lead()]\n(website + contact enrichment)
        P6[batch_apply_contact_gate()]\n(zero-contact gating)
        P7[score_lead()]\n(AI scoring agent)
        P8[generate_messages()]\n(outreach message writer)
    end

    subgraph SCR[Active scraper files in app/scrapers]
        SJD[justdial.py]
        SGM[google_maps.py]
        SCL[clutch.py]
        SSU[sulekha.py]
        SIM[indiamart_source.py]
        SIG[instagram_hashtag.py]
        SFB[facebook_pages.py]
    end

    subgraph ENR[Optional deep enricher files]
        ELN[enrichers/linkedin.py]
        ENW[enrichers/news.py]
        EIM[enrichers/indiamart.py]
    end

    subgraph DB[Database & support files]
        D1[app/database.py]\n(save, read, review, health, quality)
        D2[app/utils/lead_input.py]\n(sanitize + validate lead before DB save)
        D3[app/utils/feedback.py]\n(outcome logging + calibration)
        D4[app/review_config.py]\n(score/review thresholds)
    end

    subgraph UTILS[Utility guards]
        U1[app/utils/deduplicator.py]\n(DB duplicate dedupe)
        U2[app/utils/validator.py]\n(business validation)
        U3[app/utils/contact_gate.py]\n(zero-contact COLD gate)
    end

    %% API flow
    M1 --> P1
    M2 -.-> M1
    M3 --> D1
    M4 --> D1
    M5 --> D1
    M6 --> D1
    M7 --> D3
    M8 --> D1
    M9 --> D1

    %% Pipeline flow
    P1 --> SJD
    P1 --> SGM
    P1 --> SCL
    P1 --> SSU
    P1 --> SIM
    P1 --> SIG
    P1 --> SFB
    SJD --> P1
    SGM --> P1
    SCL --> P1
    SSU --> P1
    SIM --> P1
    SIG --> P1
    SFB --> P1

    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> P5
    P5 --> U3
    U3 --> P7
    P5 --> P7
    P7 --> P8
    P8 --> D1
    P7 --> D1
    U3 --> D1
    P5 --> D1
    P1 --> D1

    %% Enrichment details
    P5 --> ELN
    P5 --> ENW
    P5 --> EIM
    ELN --> P5
    ENW --> P5
    EIM --> P5

    %% Helper dependencies
    D1 --> D2
    D1 --> D4
    D3 --> P7
    D1 --> P7
    D3 --> M7
    D1 --> M3
    U1 --> P1
    U2 --> P1

    %% Additional feedback and quality
    P7 -.-> D3
    D1 -.-> D3
    D3 -.-> M7

    %% Notes
    classDef group fill:#f8f9fa,stroke:#d2d6dc,color:#222;
    class API,PIPE,SCR,ENR,DB,UTILS group;
```

## What the flowchart shows

- `app/main.py` is the API entry point.
- `POST /api/find-clients` launches `run_pipeline()` in `app/pipeline.py`.
- `app/pipeline.py` calls each active scraper file to collect raw leads.
- Raw leads pass through `business_qualifier.py`, `validator.py`, `pain_signals.py`, and `enricher.py`.
- `enricher.py` can optionally call `enrichers/linkedin.py`, `enrichers/news.py`, and `enrichers/indiamart.py` when `fast_mode=False`.
- `contact_gate.py` forces zero-contact leads to `COLD` and still preserves them in DB.
- `app/ai.py` scores each lead and can fall back to deterministic logic if LLM fails.
- Hot leads go through `app/messages.py` for WhatsApp / LinkedIn / email content.
- `app/database.py` saves leads, supports read endpoints, updates status/review, and logs scraper/LLM health.
- `app/utils/feedback.py` powers `/api/calibration` and adapts future scoring from Closed/Dead outcomes.

## Why this is kid-friendly

- The chart uses clear groups and labeled boxes.
- It follows a single path from request to saved output.
- It shows both the data flow and the file-level code connections.
- It avoids internal code details while keeping every file relationship visible.
