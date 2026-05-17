"""
seed_master.py — Generates 500+ realistic Indian B2B leads
Run: python seed_master.py
"""
import sqlite3, json, random, sys, os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.database import create_tables, save_lead

DB_PATH = Path(__file__).resolve().parent / "data" / "clientfinder.db"

# ── City data ─────────────────────────────────────────────────────────────────
CITIES = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
          "Pune", "Ahmedabad", "Kolkata", "Surat", "Jaipur", "Chandigarh", "Goa"]

# ── Industry → service mapping ─────────────────────────────────────────────────
INDUSTRY_SERVICES = {
    "Hospitals":      ["Website Development", "CRM Implementation", "AI Automation", "Digital Marketing"],
    "Clinics":        ["Website Development", "SEO Services", "Digital Marketing", "CRM Implementation"],
    "Restaurants":    ["SEO Services", "Social Media Marketing", "Website Development", "Digital Marketing"],
    "Hotels":         ["Digital Marketing", "SEO Services", "Social Media Marketing", "Website Development"],
    "Real Estate":    ["Digital Marketing", "CRM Implementation", "Website Development", "SEO Services"],
    "Education":      ["Website Development", "Digital Marketing", "App Development", "CRM Implementation"],
    "Gyms":           ["App Development", "Social Media Marketing", "Website Development"],
    "Salons":         ["Social Media Marketing", "Website Development", "SEO Services"],
    "Manufacturing":  ["AI Automation", "CRM Implementation", "Website Development", "ML Solutions"],
    "Retail":         ["Digital Marketing", "SEO Services", "Social Media Marketing", "Website Development"],
    "Logistics":      ["ML Solutions", "AI Automation", "CRM Implementation"],
    "IT Services":    ["AI Automation", "ML Solutions", "Digital Marketing"],
    "Fashion":        ["Social Media Marketing", "Website Development", "Digital Marketing"],
    "Travel":         ["SEO Services", "Digital Marketing", "Website Development"],
    "Legal Services": ["Website Development", "Digital Marketing", "CRM Implementation"],
    "Finance":        ["CRM Implementation", "AI Automation", "Digital Marketing"],
    "Automotive":     ["Digital Marketing", "SEO Services", "CRM Implementation"],
    "Food & Beverage":["Digital Marketing", "Social Media Marketing", "SEO Services"],
    "Healthcare":     ["AI Automation", "Website Development", "Digital Marketing"],
    "E-commerce":     ["SEO Services", "Digital Marketing", "AI Automation"],
}

# ── Name templates ─────────────────────────────────────────────────────────────
PREFIXES = ["Global", "Prime", "Royal", "Elite", "Smart", "Modern", "City",
            "Nexus", "Apex", "Metro", "Stellar", "Premier", "Urban", "Digital",
            "Bright", "Future", "Sun", "Shree", "Patel", "Kumar", "Sharma",
            "Agarwal", "Gupta", "Singh", "National", "Bharat", "Indo"]

SUFFIXES = {
    "Hospitals":      ["Hospital", "Healthcare", "Medical Centre", "Hospital & Research"],
    "Clinics":        ["Clinic", "Health Clinic", "Medical Clinic", "Polyclinic"],
    "Restaurants":    ["Restaurant", "Dhaba", "Kitchen", "Eatery", "Biryani House"],
    "Hotels":         ["Hotel", "Inn", "Residency", "Suites", "Grand Hotel"],
    "Real Estate":    ["Properties", "Developers", "Builders", "Realty", "Infra"],
    "Education":      ["Academy", "Institute", "School", "College", "Learning Hub"],
    "Gyms":           ["Fitness", "Gym", "Health Club", "Fitness Studio"],
    "Salons":         ["Salon", "Beauty Studio", "Hair Studio", "Spa"],
    "Manufacturing":  ["Industries", "Manufacturing", "Pvt Ltd", "Enterprises"],
    "Retail":         ["Store", "Mart", "Retail", "Traders"],
    "Logistics":      ["Logistics", "Cargo", "Transport", "Express"],
    "IT Services":    ["Technologies", "Tech", "IT Solutions", "Software"],
    "Fashion":        ["Fashion", "Clothing", "Boutique", "Designs"],
    "Travel":         ["Travels", "Tours", "Holidays", "Tourism"],
    "Legal Services": ["Associates", "Law Firm", "Legal", "Advocates"],
    "Finance":        ["Finance", "Investments", "Capital", "Financial Services"],
    "Automotive":     ["Auto", "Motors", "Cars", "Auto Works"],
    "Food & Beverage":["Foods", "Beverages", "Snacks", "Sweets"],
    "Healthcare":     ["Healthcare", "Wellness", "Diagnostics", "Labs"],
    "E-commerce":     ["Shop", "Commerce", "Marketplace", "Online Store"],
}

SOURCES = ["Google Maps", "JustDial", "Sulekha", "IndiaMart", "LinkedIn", "Facebook Pages"]
DOMAINS  = [".com", ".in", ".co.in", ".net", ".org"]

PAIN_TEMPLATES = {
    "Website Development": "No website or outdated HTML site, losing leads to competitors.",
    "SEO Services":        "Not ranking on Google, missing organic traffic opportunities.",
    "Social Media Marketing": "Inactive social profiles, low engagement, no brand presence.",
    "Digital Marketing":   "No online ad strategy, relying solely on word-of-mouth.",
    "CRM Implementation":  "Managing clients on Excel/WhatsApp, losing follow-ups.",
    "AI Automation":       "Manual repetitive tasks slowing operations and growth.",
    "App Development":     "No mobile app, customers can't book/order digitally.",
    "ML Solutions":        "Data-rich but insights-poor, not leveraging analytics.",
}

AI_RECOMMENDATIONS = {
    "Website Development": "Build a modern, mobile-first website with booking integration.",
    "SEO Services":        "Implement local SEO strategy to rank in top 3 results.",
    "Social Media Marketing": "Launch a 30-day content strategy across Instagram & Facebook.",
    "Digital Marketing":   "Start Google Ads + Meta campaign targeting local customers.",
    "CRM Implementation":  "Deploy lightweight CRM to track leads and automate follow-ups.",
    "AI Automation":       "Automate intake forms, scheduling, and follow-up emails.",
    "App Development":     "Launch a branded mobile app for bookings and loyalty.",
    "ML Solutions":        "Build a customer churn prediction model using existing data.",
}

def _slug(name: str) -> str:
    return name.lower().replace(" ", "").replace("&", "and").replace("'", "")[:20]

def _score(has_website: bool, has_phone: bool, has_email: bool) -> int:
    base = random.randint(60, 80)
    if has_website: base += random.randint(3, 8)
    if has_phone:   base += random.randint(3, 7)
    if has_email:   base += random.randint(2, 6)
    return min(base, 98)

def _label(score: int) -> str:
    if score >= 85: return "HOT"
    if score >= 70: return "WARM"
    return "COLD"

def _growth(score: int) -> str:
    if score >= 85: return "High"
    if score >= 70: return "Medium"
    return "Low"

def _quality(score: int) -> str:
    if score >= 85: return "Premium"
    if score >= 70: return "Good"
    return "Fair"

def generate_lead(city: str, industry: str, service: str) -> dict:
    prefix = random.choice(PREFIXES)
    suffix = random.choice(SUFFIXES.get(industry, ["Solutions"]))
    name   = f"{prefix} {suffix} {city[:3]}"

    slug      = _slug(name)
    domain    = random.choice(DOMAINS)
    website   = f"http://www.{slug}{domain}" if random.random() > 0.25 else ""
    has_web   = bool(website)
    has_phone = random.random() > 0.1
    has_email = random.random() > 0.15

    phone = ""
    email = ""
    if has_phone:
        phone = f"+91-{random.randint(70,99)}{random.randint(10000000,99999999)}"
    if has_email:
        email = f"info@{slug}{domain}"

    score = _score(has_web, has_phone, has_email)
    label = _label(score)

    pain   = PAIN_TEMPLATES.get(service, "Needs digital transformation.")
    ai_rec = AI_RECOMMENDATIONS.get(service, "Implement a tailored digital growth strategy.")

    return {
        "company_name":      name,
        "city":              city,
        "category":          service,   # industry field in DB = service category
        "source":            random.choice(SOURCES),
        "phone":             phone,
        "email":             email,
        "website":           website,
        "website_alive":     has_web,
        "fit_score":         random.randint(65, 95),
        "intent_score":      random.randint(70, 99),
        "contact_score":     random.randint(75, 100) if (has_phone or has_email) else 20,
        "composite_score":   score,
        "label":             label,
        "pain_point":        pain,
        "decision_maker":    random.choice(["Owner", "Director", "Manager", "Founder", "CEO"]),
        "buying_signals":    json.dumps(["Looking for vendor", "Budget approved", "Active searches"]),
        "objection_1":       "Budget constraints right now",
        "rebuttal_1":        "We work on flexible payment plans with clear ROI targets.",
        "objection_2":       "Currently working with someone else",
        "rebuttal_2":        "We offer a free audit — no commitment needed.",
        "best_channel":      random.choice(["WhatsApp", "Email", "LinkedIn", "Phone"]),
        "personalized_opener": f"Hi, I noticed {name} in {city} could significantly benefit from {service}.",
        "whatsapp_msg":      f"Hi! I'm reaching out to {name}. We help {industry} businesses in {city} with {service}. Can we chat?",
        "linkedin_msg":      f"Hello! We specialize in {service} for {industry} in {city}. Would love to connect and share some ideas.",
        "email_subject":     f"Quick idea for {name} — {service}",
        "email_msg":         f"Hi,\n\n{pain}\n\nWe've helped similar businesses in {city} with {service}. {ai_rec}\n\nOpen to a 15-min call?\n\nBest,\nClientFinder Team",
        "hot_reason":        ai_rec,
        "description":       f"{industry} business in {city} identified as high-potential for {service}.",
        "review_status":     "approved",
        "status":            "New",
        "pain_signals_json": json.dumps({
            "negative_reviews_found": random.choice([True, False]),
            "website_is_outdated":    not has_web or random.random() > 0.5,
            "no_google_maps_listing": random.random() > 0.4,
            "website_not_mobile":     not has_web or random.random() > 0.6,
            "last_social_post_old":   random.random() > 0.4,
        }),
        # Extra demo fields stored in description
        "industry_tag":      industry,
        "growth_potential":  _growth(score),
        "lead_quality":      _quality(score),
        "ai_recommendation": ai_rec,
        "budget_range":      random.choice(["< ₹25k", "₹25k–₹1L", "₹1L–₹5L", "> ₹5L"]),
    }

def run():
    print("Clearing existing leads…")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM leads")
    try:
        conn.execute("DELETE FROM sqlite_sequence WHERE name='leads'")
    except Exception:
        pass
    conn.commit()
    conn.close()

    create_tables()

    count = 0
    seen  = set()
    for city in CITIES:
        for industry, services in INDUSTRY_SERVICES.items():
            # 3–5 leads per city/industry/service combination
            for service in services:
                num = random.randint(3, 5)
                for _ in range(num):
                    lead = generate_lead(city, industry, service)
                    key  = (lead["company_name"], lead["city"])
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        save_lead(lead)
                        count += 1
                    except Exception as e:
                        pass  # skip duplicates

    print(f"Done! {count} leads inserted across {len(CITIES)} cities and {len(INDUSTRY_SERVICES)} industries.")

if __name__ == "__main__":
    run()
