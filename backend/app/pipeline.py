"""
pipeline.py
============
ClientFinder Pipeline Orchestrator
-------------------------------------
Runs all 9 stages in sequence for a search request.

Stage 1  → Dedup gate              (skip known companies before scraping)
Stage 2  → Scrape 7 sources        (concurrent — all scrapers run in parallel)
Stage 2.5→ Pain Signal Detection   (Google reviews, social activity, website check)
Stage 3  → Clean + Validate        (remove junk names, zero-contact leads)
Stage 4  → Enrich                  (website discovery, email/phone extraction)
Stage 5  → Contact gate            (force COLD if still no contact after enrichment)
Stage 6  → AI Scoring              (fit / intent / contact scores via Ollama)
Stage 6.5→ Client Readiness Score  (deterministic money+pain+reachability score)
Stage 7  → Message generation      (pain-specific WhatsApp + LinkedIn + Email)
Stage 8  → Save to database        (persist all scored leads)

Sources (active): JustDial, Google Maps, Clutch, Sulekha,
                  IndiaMART, Instagram, Facebook Pages
Sources (disabled — job boards, low quality): Freelancer, Truelancer, Internshala, Reddit, TradeIndia

Returns structured results with HOT / WARM / COLD counts.
"""

import asyncio
from datetime import date

# Scrapers — ACTIVE (real businesses, not job boards)
from app.scrapers.justdial import scrape_justdial
from app.scrapers.google_maps import scrape_google_maps
from app.scrapers.clutch import scrape_clutch
from app.scrapers.sulekha import scrape_sulekha
from app.scrapers.indiamart_source import scrape_indiamart
from app.scrapers.instagram_hashtag import scrape_instagram_hashtag
from app.scrapers.facebook_pages import scrape_facebook_pages
# from app.scrapers.tradeindia import scrape_tradeindia

# Scrapers — RE-ENABLED with BusinessQualifier gate (filters individuals, microbudgets, dead posts)

# Scrapers — still disabled (intern-level, not buyers)
from app.scrapers.freelancer import scrape_freelancer
from app.scrapers.reddit import scrape_reddit
# from app.scrapers.truelancer import scrape_truelancer
# from app.scrapers.internshala import scrape_internshala

# Pain Signal Detection
from app.pain_signals import batch_detect_pain_signals

# Business Qualifier filter (runs right after scraping, before enrichment)
from app.filters.business_qualifier import tag_directory_leads

# Enrichment
from app.enricher import enrich_lead

# AI
from app.ai import (
    score_lead,
    compute_client_readiness_score,
    _rule_based_scoring_fallback,
)

# Messages
from app.messages import generate_messages

# Utils
from app.utils.deduplicator import batch_filter_duplicates
from app.utils.validator import filter_valid_leads
from app.utils.contact_gate import batch_apply_contact_gate

# Database
from app.database import ensure_db, save_lead, is_duplicate, log_scraper_run


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deduplicate_within_batch(leads: list[dict]) -> list[dict]:
    """
    Remove duplicates within the current batch (before DB check).
    Two scrapers often return the same company.
    Prefers leads with more data (phone > no phone).
    """
    seen: dict[str, dict] = {}
    for lead in leads:
        # Key = normalised company_name + city
        key = (
            (lead.get("company_name") or "").lower().strip(),
            (lead.get("location") or "").lower().strip(),
        )
        if not key[0]:
            continue
        if key not in seen:
            seen[key] = lead
        else:
            # Prefer the version with more contact data
            existing = seen[key]
            existing_contacts = sum([
                bool(existing.get("phone")),
                bool(existing.get("email")),
                bool(existing.get("website")),
            ])
            new_contacts = sum([
                bool(lead.get("phone")),
                bool(lead.get("email")),
                bool(lead.get("website")),
            ])
            if new_contacts > existing_contacts:
                seen[key] = lead  # replace with better version

    return list(seen.values())


def _build_result(lead: dict) -> dict:
    """Build a clean result dict from a fully processed lead."""
    # Collect which pain signals fired for the review UI
    pain_signals_summary = {
        "negative_reviews":    lead.get("negative_reviews_found") is True,
        "no_maps_listing":     lead.get("no_google_maps_listing") is True,
        "outdated_website":    lead.get("website_is_outdated") is True,
        "not_mobile_friendly": lead.get("website_not_mobile") is True,
        "inactive_social":     lead.get("last_social_post_old") is True,
        "review_complaint":    lead.get("review_complaint", ""),
    }

    return {
        "id":                       lead.get("_db_id"),
        "company_name":             lead.get("company_name", ""),
        "city":                     lead.get("location", lead.get("city", "")),
        "industry":                 lead.get("industry", lead.get("category", "")),
        "source":                   lead.get("source", ""),
        "source_url":               lead.get("source_url", ""),
        "contact_link":             lead.get("contact_link", lead.get("source_url", "")),
        "phone":                    lead.get("phone", ""),
        "email":                    lead.get("email", ""),
        "website":                  lead.get("website", ""),
        "linkedin_url":             lead.get("linkedin_url", ""),
        "instagram_handle":         lead.get("instagram_handle", ""),
        "website_alive":            bool(lead.get("website_alive")),
        "company_size":             lead.get("company_size", ""),
        # AI scores
        "fit_score":                int(lead.get("fit_score", 0)),
        "intent_score":             int(lead.get("intent_score", lead.get("buying_intent_score", 0))),
        "contact_score":            int(lead.get("contact_score", lead.get("contactability_score", 0))),
        "composite_score":          float(lead.get("composite_score", 0.0)),
        # Client Readiness Score (deterministic: money + pain + reachability)
        "client_readiness_score":   int(lead.get("client_readiness_score", 0)),
        # Labels
        "label":                    lead.get("label", lead.get("priority_tag", "COLD")),
        "hot_reason":               lead.get("hot_reason", lead.get("score_reason", "")),
        # Intel
        "pain_point":               lead.get("pain_point", ""),
        "pain_signals":             pain_signals_summary,
        "pain_template":            lead.get("pain_template", ""),
        "decision_maker":           lead.get("decision_maker", ""),
        "estimated_deal_size":      lead.get("estimated_deal_size", lead.get("estimated_deal", "")),
        "intent_signal":            lead.get("intent_signal", ""),
        # Outreach
        "whatsapp_msg":             lead.get("whatsapp_msg", ""),
        "whatsapp_variants":        lead.get("whatsapp_variants", []),
        "linkedin_msg":             lead.get("linkedin_msg", ""),
        "email_subject":            lead.get("email_subject", ""),
        "email_msg":                lead.get("email_msg", ""),
        "status":                   lead.get("status", "New"),
    }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(
    service: str,
    city: str,
    industry: str,
    budget_range: str = "₹50k–₹2L",
    max_leads: int = 30,
    fast_mode: bool = True,
    on_progress=None,           # optional callback: on_progress(stage, message)
) -> dict:
    """
    Run the full 8-stage ClientFinder pipeline.

    Args:
        service:      What Broader AI offers e.g. "AI automation for businesses"
        city:         Target city e.g. "Delhi", "Mumbai"
        industry:     Target industry / keyword e.g. "hospitals", "restaurants"
        budget_range: Deal size context for AI scoring e.g. "₹50k–₹2L"
        max_leads:    Max leads to return (default 30)

    Returns:
        {
          "total_scraped_raw": int,
          "total_after_prefilter": int,
          "total_after_dedup": int,
          "total_after_enrichment": int,
          "total_saved": int,
          "hot": int, "warm": int, "cold": int,
          "leads": [...]     ← HOT first, then WARM (top 5), COLD excluded
        }
    """
    ensure_db()
    context = {
        "service":      service,
        "city":         city,
        "industry":     industry,
        "budget_range": budget_range,
        "fast_mode":    fast_mode,
    }

    print(f"\n{'='*60}")
    print(f"[PIPELINE] service={service!r} | city={city!r} | industry={industry!r}")
    print(f"{'='*60}")

    # ── Stage 1: Pre-flight dedup (DB-level fast check) ───────────────────
    # We skip this stage at scraping level — dedup happens after scraping
    # because scrapers are cheap; enrichment + LLM calls are expensive.

    # ── Stage 2: Scrape 7 quality sources concurrently ────────────────────
    # Old job-board sources (Freelancer, Truelancer, Internshala, Reddit)
    # are DISABLED — they find people already shopping around, not true clients.
    print("\n[STAGE 2] Scraping quality sources in parallel...")
    if on_progress: on_progress("scraping", "Scraping quality sources in parallel...")
    scrape_results = await asyncio.gather(
        scrape_justdial(industry, city),
        scrape_google_maps(industry, city),
        scrape_clutch(industry, city),
        scrape_sulekha(industry, city),
        scrape_indiamart(industry, city),
        scrape_instagram_hashtag(industry, city),
        scrape_facebook_pages(industry, city),
        return_exceptions=True,
    )

    source_names = [
        "justdial", "google_maps", "clutch", "sulekha",
        "indiamart", "instagram", "facebook",
    ]

    source_stats = {name: {"attempted": 0, "saved": 0, "failed": False} for name in source_names}

    def _finalize_scraper_logs():
        # ── Log scraper health metrics ────────────────────────────────────────
        for name, stats in source_stats.items():
            if stats["failed"]:
                try: log_scraper_run(source=name, attempted=0, saved=0, rejected=0)
                except Exception as e: print(f"  [{name:12}] WARNING: scraper_run log failed: {e}")
            else:
                att = stats["attempted"]
                sav = stats["saved"]
                try: log_scraper_run(source=name, attempted=att, saved=sav, rejected=max(0, att - sav))
                except Exception as e: print(f"  [{name:12}] WARNING: scraper_run log failed: {e}")

    raw_leads: list[dict] = []
    for name, result in zip(source_names, scrape_results):
        if isinstance(result, list):
            attempted = len(result)
            source_stats[name]["attempted"] = attempted
            print(f"  [{name:12}] {attempted} leads")
            for lead in result:
                lead["source"] = lead.get("source") or name
            raw_leads.extend(result)
        else:
            print(f"  [{name:12}] ERROR: {result}")
            source_stats[name]["failed"] = True

    print(f"[STAGE 2] Total raw: {len(raw_leads)}")

    total_scraped_raw = len(raw_leads)

    if not raw_leads:
        _finalize_scraper_logs()
        return {
            "total_scraped_raw": total_scraped_raw, "total_after_prefilter": 0,
            "total_after_dedup": 0, "total_after_enrichment": 0, "total_saved": 0,
            "hot": 0, "warm": 0, "cold": 0, "leads": []
        }

    # ── Stage 2.2: Business Qualifier Gate ────────────────────────────────
    # Tag the active sources with source_intent_level metadata for scoring.
    print(f"\n[STAGE 2.2] Running BusinessQualifier on {len(raw_leads)} raw leads...")
    if on_progress: on_progress("qualifying", f"Tagging {len(raw_leads)} leads for scoring...")

    raw_leads = tag_directory_leads(raw_leads)
    print(f"[STAGE 2.2] Tagged {len(raw_leads)} leads with source intent metadata")

    # ── Stage 2.5: Pain Signal Detection ──────────────────────────────────
    # Lightweight pass — DDG lookups for Google reviews, social activity,
    # website freshness. No LLM. Runs BEFORE clean so even junk leads get
    # signals (in case a lead is rescued by a strong pain score).
    prefiltered_leads = filter_valid_leads(
        raw_leads,
        target_industry=industry,
        target_city=city,
    )
    if len(prefiltered_leads) != len(raw_leads):
        print(f"[STAGE 2.3] Prefiltered {len(raw_leads) - len(prefiltered_leads)} invalid leads before pain signals")
    raw_leads = prefiltered_leads
    total_after_prefilter = len(raw_leads)

    print(f"\n[STAGE 2.5] Detecting pain signals for {len(raw_leads)} leads...")
    if on_progress: on_progress("pain_signals", f"Scanning {len(raw_leads)} leads for pain signals (reviews, website, social)...")
    raw_leads = await batch_detect_pain_signals(raw_leads, batch_size=8)
    signals_found = sum(
        1 for l in raw_leads if any(l.get(k) is True for k in [
            "negative_reviews_found", "no_google_maps_listing",
            "website_is_outdated", "website_not_mobile", "last_social_post_old"
        ])
    )
    print(f"[STAGE 2.5] Pain signals detected on {signals_found}/{len(raw_leads)} leads")

    # ── Stage 3: Clean + Validate ─────────────────────────────────────────
    print(f"\n[STAGE 3] Validating + deduplicating...")
    if on_progress: on_progress("validating", "Cleaning and deduplicating leads...")


    # Remove junk names and zero-contact leads
    validated = filter_valid_leads(
        raw_leads,
        target_industry=industry,
        target_city=city,
    )

    # Remove duplicates within this batch
    deduplicated_batch = _deduplicate_within_batch(validated)

    # Remove leads already in DB (dedup against historical data)
    new_leads = batch_filter_duplicates(deduplicated_batch)

    total_after_dedup = len(new_leads)
    print(f"[STAGE 3] After dedup: {len(new_leads)} new leads to process")

    if not new_leads:
        _finalize_scraper_logs()
        return {
            "total_scraped_raw": total_scraped_raw, "total_after_prefilter": total_after_prefilter,
            "total_after_dedup": total_after_dedup, "total_after_enrichment": 0, "total_saved": 0,
            "hot": 0, "warm": 0, "cold": 0, "leads": [],
            "message": "All leads already in database."
        }

    # ── Stage 4: Enrich (concurrent, capped to avoid overload) ───────────
    print(f"\n[STAGE 4] Enriching {len(new_leads)} leads...")
    if on_progress: on_progress("enriching", f"Enriching {len(new_leads)} leads (website, email, phone)...")


    # Process in batches of 10 to avoid overwhelming DDG/httpx
    _BATCH_SIZE = 10
    enriched_leads: list[dict] = []
    for i in range(0, len(new_leads), _BATCH_SIZE):
        batch = new_leads[i: i + _BATCH_SIZE]
        results = await asyncio.gather(
            *[enrich_lead(lead, fast_mode=fast_mode) for lead in batch],
            return_exceptions=True,
        )
        for lead, result in zip(batch, results):
            if isinstance(result, dict):
                enriched_leads.append(result)
            else:
                print(f"  [enrich] failed for '{lead.get('company_name')}': {result}")
                enriched_leads.append(lead)  # use un-enriched version

    total_after_enrichment = len(enriched_leads)
    print(f"[STAGE 4] Enrichment complete: {len(enriched_leads)} leads")

    # ── Stage 5: Contact gate ─────────────────────────────────────────────
    print("\n[STAGE 5] Applying contact gate...")
    if on_progress: on_progress("contact_gate", "Filtering leads without contact info...")

    actionable, gated = batch_apply_contact_gate(enriched_leads)
    print(f"[STAGE 5] actionable={len(actionable)}, gated={len(gated)}")

    # ── Stage 6: AI Scoring ───────────────────────────────────────────────
    print(f"\n[STAGE 6] AI scoring {len(actionable)} leads...")
    if on_progress: on_progress("ai_scoring", f"AI scoring {len(actionable)} leads via Ollama...")


    scored_leads: list[dict] = []
    for i, lead in enumerate(actionable):
        # Live counter update so job status shows progress
        if on_progress:
            on_progress(
                "ai_scoring",
                f"AI scoring lead {i+1}/{len(actionable)}: {lead.get('company_name','')[:30]}..."
            )
        try:
            # Per-lead hard cap — if Ollama stalls on one lead, skip it after 55s
            scores = await asyncio.wait_for(score_lead(lead, context), timeout=90.0)
            if not scores:
                raise ValueError("empty response")
            merged = {**lead, **scores}
            # Map field names to our schema
            merged["intent_score"]  = scores.get("buying_intent_score", scores.get("intent_score", 0))
            merged["contact_score"] = scores.get("contactability_score", scores.get("contact_score", 0))
            merged["label"]         = scores.get("priority_tag", scores.get("label", "COLD"))
            merged["hot_reason"]    = scores.get("score_reason", scores.get("hot_reason", ""))
            scored_leads.append(merged)
        except asyncio.TimeoutError:
            print(f"  [score] TIMEOUT for '{lead.get('company_name')}' — using deterministic fallback")
            fallback_scores = _rule_based_scoring_fallback(lead)
            fallback_scores["score_reason"] = "Scoring timed out — deterministic fallback used."
            fallback_scores["hot_reason"] = fallback_scores["score_reason"]
            merged = {**lead, **fallback_scores}
            merged["intent_score"] = fallback_scores.get("buying_intent_score", fallback_scores.get("intent_score", 0))
            merged["contact_score"] = fallback_scores.get("contactability_score", fallback_scores.get("contact_score", 0))
            merged["label"] = fallback_scores.get("priority_tag", fallback_scores.get("label", "COLD"))
            scored_leads.append(merged)
        except Exception as e:
            print(f"  [score] failed for '{lead.get('company_name')}': {e}")
            fallback_scores = _rule_based_scoring_fallback(lead)
            fallback_scores["score_reason"] = f"Scoring unavailable — deterministic fallback used. Error: {e}"
            fallback_scores["hot_reason"] = fallback_scores["score_reason"]
            merged = {**lead, **fallback_scores}
            merged["intent_score"] = fallback_scores.get("buying_intent_score", fallback_scores.get("intent_score", 0))
            merged["contact_score"] = fallback_scores.get("contactability_score", fallback_scores.get("contact_score", 0))
            merged["label"] = fallback_scores.get("priority_tag", fallback_scores.get("label", "COLD"))
            scored_leads.append(merged)


    # Include gated leads (already forced to COLD)
    all_scored = scored_leads + gated
    print(f"[STAGE 6] Scoring complete: {len(scored_leads)} scored + {len(gated)} gated")

    # ── Stage 6.5: Client Readiness Score ─────────────────────────────────
    # Deterministic score: money signals + pain signals + reachability.
    # Stored as client_readiness_score on each lead.
    # Does NOT change the HOT/WARM/COLD label — purely informational for now.
    print("\n[STAGE 6.5] Computing client readiness scores...")
    if on_progress: on_progress("readiness_score", "Computing client readiness scores...")
    for lead in all_scored:
        lead["client_readiness_score"] = compute_client_readiness_score(lead)
        weighted_score = lead.get("composite_score", 0)
        if lead.get("client_readiness_score", 0) >= 70 and weighted_score >= 60:
            weighted_score = min(weighted_score + 5, 100)
            lead["composite_score"] = weighted_score
    avg_readiness = (
        sum(l.get("client_readiness_score", 0) for l in all_scored) / len(all_scored)
        if all_scored else 0
    )
    print(f"[STAGE 6.5] Avg readiness score: {avg_readiness:.1f}/100")

    # Separate by label
    hot  = [l for l in all_scored if l.get("label") == "HOT"]
    warm = [l for l in all_scored if l.get("label") == "WARM"]
    cold = [l for l in all_scored if l.get("label") == "COLD"]

    hot.sort(key=lambda x: float(x.get("composite_score") or 0), reverse=True)
    print(f"[STAGE 6] HOT={len(hot)} | WARM={len(warm)} | COLD={len(cold)}")

    # ── Stage 7: Message generation (HOT leads only) ──────────────────────
    top_hot = hot[:10]
    if top_hot:
        print(f"\n[STAGE 7] Generating messages for {len(top_hot)} HOT leads...")
        if on_progress: on_progress("messages", f"Writing outreach messages for {len(top_hot)} HOT leads...")
        msg_results = await asyncio.gather(
            *[generate_messages(lead, context) for lead in top_hot],
            return_exceptions=True,
        )
        for lead, msgs in zip(top_hot, msg_results):
            if isinstance(msgs, dict):
                lead["whatsapp_msg"]      = msgs.get("whatsapp", "")
                lead["whatsapp_variants"] = msgs.get("whatsapp_variants", [])
                lead["linkedin_msg"]      = msgs.get("linkedin", "")
                lead["email_subject"]     = msgs.get("email_subject", "")
                lead["email_msg"]         = msgs.get("email_body", "")
        print(f"[STAGE 7] Messages generated")

    # ── Stage 8: Save to database ─────────────────────────────────────────
    print(f"\n[STAGE 8] Saving {len(all_scored)} leads to DB...")
    if on_progress: on_progress("saving", f"Saving {len(all_scored)} leads to database...")

    saved = 0
    for lead in all_scored:
        try:
            db_id = save_lead(lead)
            lead["_db_id"] = db_id
            saved += 1
            source = lead.get("source", "")
            if source in source_stats:
                source_stats[source]["saved"] += 1
        except Exception as e:
            print(f"  [DB] save failed for '{lead.get('company_name')}': {e}")

    _finalize_scraper_logs()

    print(f"[STAGE 8] Saved {saved} leads")
    print(f"\n[PIPELINE] Done! HOT={len(hot)} | WARM={len(warm)} | COLD={len(cold)}\n")

    # ── Build response ────────────────────────────────────────────────────
    response_leads = [_build_result(l) for l in top_hot]
    response_leads += [_build_result(l) for l in warm[:5]]

    return {
        "total_scraped_raw":      total_scraped_raw,
        "total_after_prefilter":  total_after_prefilter,
        "total_after_dedup":      total_after_dedup,
        "total_after_enrichment": total_after_enrichment,
        "total_saved":            saved,
        "hot":                    len(hot),
        "warm":                   len(warm),
        "cold":                   len(cold),
        "leads":                  response_leads[:max_leads],
        "scrape_date":            date.today().isoformat(),
    }


async def run_intent_pipeline(
    service: str,
    city: str,
    industry: str,
    budget_range: str = "₹50k-₹2L",
    max_leads: int = 20,
    on_progress=None,
) -> dict:
    """
    Intent pipeline:
    - Runs active-request sources separately from directory sources
    - Keeps direct source/post links
    - Scores without the directory contact gate so active buyer signals can surface
    """
    ensure_db()
    context = {
        "service": service,
        "city": city,
        "industry": industry,
        "budget_range": budget_range,
        "fast_mode": True,
    }

    print(f"\n[INTENT PIPELINE] city={city!r} | industry={industry!r}")
    if on_progress:
        on_progress("intent_scraping", "Scraping active-request sources (Freelancer, Reddit)...")

    scrape_results = await asyncio.gather(
        scrape_freelancer(industry, city),
        scrape_reddit(industry, city),
        return_exceptions=True,
    )

    source_names = ["freelancer", "reddit"]
    raw_leads: list[dict] = []
    for name, result in zip(source_names, scrape_results):
        if isinstance(result, list):
            print(f"  [intent:{name:10}] {len(result)} leads")
            for lead in result:
                lead["source"] = lead.get("source") or name
            raw_leads.extend(result)
        else:
            print(f"  [intent:{name:10}] ERROR: {result}")

    total_scraped_raw = len(raw_leads)
    if not raw_leads:
        return {
            "total_scraped_raw": 0,
            "total_saved": 0,
            "hot": 0,
            "warm": 0,
            "cold": 0,
            "leads": [],
            "scrape_date": date.today().isoformat(),
        }

    deduplicated_batch = _deduplicate_within_batch(raw_leads)
    new_leads = batch_filter_duplicates(deduplicated_batch)
    print(f"[INTENT PIPELINE] After dedup: {len(new_leads)}")

    if on_progress:
        on_progress("intent_scoring", f"Scoring {len(new_leads)} intent leads...")

    scored_leads: list[dict] = []
    for i, lead in enumerate(new_leads):
        if on_progress:
            on_progress(
                "intent_scoring",
                f"Scoring intent lead {i + 1}/{len(new_leads)}: {lead.get('company_name', '')[:30]}...",
            )
        try:
            scores = await asyncio.wait_for(score_lead(lead, context), timeout=90.0)
            if not scores:
                raise ValueError("empty response")
            merged = {**lead, **scores}
            merged["intent_score"] = scores.get("buying_intent_score", scores.get("intent_score", 0))
            merged["contact_score"] = scores.get("contactability_score", scores.get("contact_score", 0))
            merged["label"] = scores.get("priority_tag", scores.get("label", "COLD"))
            merged["hot_reason"] = scores.get("score_reason", scores.get("hot_reason", ""))
            scored_leads.append(merged)
        except Exception as e:
            print(f"  [intent score] failed for '{lead.get('company_name')}': {e}")
            fallback_scores = _rule_based_scoring_fallback(lead)
            fallback_scores["score_reason"] = (
                f"Intent scoring fallback used. Error: {e}"
            )
            merged = {**lead, **fallback_scores}
            merged["intent_score"] = fallback_scores.get("buying_intent_score", fallback_scores.get("intent_score", 0))
            merged["contact_score"] = fallback_scores.get("contactability_score", fallback_scores.get("contact_score", 0))
            merged["label"] = fallback_scores.get("priority_tag", fallback_scores.get("label", "COLD"))
            merged["hot_reason"] = fallback_scores.get("score_reason", "")
            scored_leads.append(merged)

    for lead in scored_leads:
        lead["client_readiness_score"] = compute_client_readiness_score(lead)
        weighted_score = lead.get("composite_score", 0)
        if lead.get("client_readiness_score", 0) >= 70 and weighted_score >= 60:
            weighted_score = min(weighted_score + 5, 100)
            lead["composite_score"] = weighted_score

    hot = [l for l in scored_leads if l.get("label") == "HOT"]
    warm = [l for l in scored_leads if l.get("label") == "WARM"]
    cold = [l for l in scored_leads if l.get("label") == "COLD"]
    hot.sort(key=lambda x: float(x.get("composite_score") or 0), reverse=True)
    warm.sort(key=lambda x: float(x.get("composite_score") or 0), reverse=True)
    cold.sort(key=lambda x: float(x.get("composite_score") or 0), reverse=True)

    saved = 0
    for lead in scored_leads:
        try:
            db_id = save_lead(lead)
            lead["_db_id"] = db_id
            saved += 1
        except Exception as e:
            print(f"  [INTENT DB] save failed for '{lead.get('company_name')}': {e}")

    response_leads = [_build_result(l) for l in (hot + warm + cold)[:max_leads]]
    print(f"[INTENT PIPELINE] HOT={len(hot)} | WARM={len(warm)} | COLD={len(cold)}")

    return {
        "total_scraped_raw": total_scraped_raw,
        "total_saved": saved,
        "hot": len(hot),
        "warm": len(warm),
        "cold": len(cold),
        "leads": response_leads,
        "scrape_date": date.today().isoformat(),
    }
