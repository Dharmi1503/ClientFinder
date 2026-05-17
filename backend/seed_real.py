"""seed_real.py — Seeds DB with 100+ real verified Indian businesses as mock data."""
import json, random, sqlite3, sys, os
from pathlib import Path
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.database import create_tables, save_lead

DB = Path(__file__).resolve().parent / "data" / "clientfinder.db"
DATA = Path(__file__).resolve().parent / "real_businesses.json"

INDUSTRY_SERVICES = {
    "Hospitals":   ["Website Development","CRM Implementation","AI Automation","Digital Marketing"],
    "Clinics":     ["CRM Implementation","AI Automation","Website Development","SEO Services"],
    "Real Estate": ["Digital Marketing","CRM Implementation","Website Development","SEO Services"],
    "Restaurants": ["SEO Services","Digital Marketing","Website Development"],
    "Gyms":        ["Website Development","Digital Marketing","SEO Services"],
    "Salons":      ["SEO Services","Digital Marketing","Website Development"],
    "Hotels":      ["SEO Services","Website Development","Digital Marketing"],
    "Schools":     ["CRM Implementation","Website Development","Digital Marketing"],
}

AI_REC = {
    "Website Development": "Outdated or missing website detected — losing potential clients to competitors with modern online presence.",
    "SEO Services":        "Not ranking on Google local searches — missing 70% of high-intent organic traffic.",
    "Digital Marketing":   "No active Google Ads or social media campaigns — brand visibility critically low.",
    "CRM Implementation":  "No CRM system found — leads likely managed on spreadsheets, causing revenue leakage.",
    "AI Automation":       "Manual repetitive tasks slowing operations — automation can save 15+ hours per week.",
}

SOURCES_REAL = ["Google Maps","JustDial","Sulekha","LinkedIn","Facebook Pages"]

def score_lead(biz):
    s = 70
    if biz.get("website"): s += random.randint(5, 12)
    if biz.get("phone"):   s += random.randint(3, 8)
    if biz.get("email"):   s += random.randint(3, 8)
    return min(int(s), 98)

def label(s): return "HOT" if s>=85 else ("WARM" if s>=70 else "COLD")
def growth(s): return "High" if s>=85 else ("Medium" if s>=70 else "Low")
def quality(s): return "Premium" if s>=85 else ("Good" if s>=70 else "Fair")

def last_active(s):
    d = random.randint(1,4) if s>=85 else (random.randint(5,21) if s>=70 else random.randint(30,90))
    return (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")

def run():
    conn = sqlite3.connect(str(DB))
    conn.execute("DELETE FROM leads")
    try: conn.execute("DELETE FROM sqlite_sequence WHERE name='leads'")
    except: pass
    conn.commit(); conn.close()
    create_tables()

    businesses = json.loads(DATA.read_text(encoding="utf-8"))
    total = 0
    for biz in businesses:
        industry = biz["industry"]
        services = INDUSTRY_SERVICES.get(industry, ["Digital Marketing"])
        for service in services:
            s = score_lead(biz)
            rec = AI_REC.get(service, "Implement a tailored digital growth strategy.")
            lead = {
                "company_name":      biz["name"],
                "city":              biz["city"],
                "category":          service,
                "source":            biz.get("source", random.choice(SOURCES_REAL)),
                "phone":             biz.get("phone",""),
                "email":             biz.get("email",""),
                "website":           biz.get("website",""),
                "website_alive":     bool(biz.get("website")),
                "fit_score":         random.randint(65,95),
                "intent_score":      s,
                "contact_score":     90 if biz.get("phone") and biz.get("email") else (65 if biz.get("phone") or biz.get("email") else 30),
                "composite_score":   float(s),
                "label":             label(s),
                "pain_point":        rec,
                "hot_reason":        rec,
                "decision_maker":    random.choice(["Owner","Director","CEO","Founder","Marketing Head"]),
                "buying_signals":    json.dumps(["Active online presence","Industry benchmark gaps","Growth phase"]),
                "objection_1":       "We already have someone handling this",
                "rebuttal_1":        "We offer a free audit — zero commitment required.",
                "objection_2":       "Budget is tight right now",
                "rebuttal_2":        "Flexible payment plans with clear ROI milestones.",
                "best_channel":      "Email" if biz.get("email") else "Phone",
                "personalized_opener": f"Hi {biz['name']} team — we noticed an opportunity to improve your {service} significantly.",
                "whatsapp_msg":      f"Hi! Reaching out to {biz['name']}. We help {industry} businesses with {service} in {biz['city']}. Open to a quick chat?",
                "linkedin_msg":      f"Hello! We specialize in {service} for {industry} in {biz['city']}. Would love to connect.",
                "email_subject":     f"{service} strategy for {biz['name']}",
                "email_msg":         f"Hi team,\n\n{rec}\n\nWe've helped similar {industry} businesses in {biz['city']} with {service}.\n\nAre you open to a 15-min call?\n\nBest,\nClientFinder Team",
                "review_status":     "approved",
                "status":            "New",
                "description":       f"REAL BUSINESS — {industry} in {biz['city']}. Source: {biz.get('source','Google Maps')}. Service needed: {service}.",
                "pain_signals_json": json.dumps({
                    "website_is_outdated": not bool(biz.get("website")),
                    "no_google_maps_listing": False,
                    "website_not_mobile": random.choice([True,False]),
                    "last_social_post_old": random.choice([True,False]),
                    "negative_reviews_found": False,
                }),
                "growth_potential":  growth(s),
                "lead_quality":      quality(s),
                "ai_recommendation": rec,
                "industry_tag":      industry,
                "last_active":       last_active(s),
            }
            try:
                save_lead(lead)
                total += 1
            except Exception as e:
                print(f"Skip: {biz['name']} / {service} — {e}")

    print(f"Done! {total} real-business leads seeded across all city/industry/service combos.")

if __name__ == "__main__":
    run()
