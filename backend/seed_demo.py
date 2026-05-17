"""
seed_demo.py
============
Generates curated, demo-ready B2B leads for the ClientFinder SaaS demo.

Distribution per valid city+industry+service combination:
  HOT  : 3-5  leads  (score 90-98, full contact, recent activity)
  WARM : 8-15 leads  (score 75-89, partial contact)
  COLD : 15-25 leads (score 60-74, weak/no contact)

Run: python seed_demo.py
"""

import sqlite3, json, random, sys, os
from pathlib import Path
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.database import create_tables, save_lead

DB_PATH = Path(__file__).resolve().parent / "data" / "clientfinder.db"

# ── Valid city+industry+service combos only ────────────────────────────────────
CITIES = ["Mumbai", "Delhi NCR", "Bangalore", "Hyderabad", "Pune", "Ahmedabad"]

VALID_COMBOS = [
    # Hospitals
    ("Hospitals",   "Website Development"),
    ("Hospitals",   "CRM Implementation"),
    ("Hospitals",   "AI Automation"),
    # Restaurants
    ("Restaurants", "SEO Services"),
    ("Restaurants", "Digital Marketing"),
    ("Restaurants", "Website Development"),
    # Real Estate
    ("Real Estate", "Digital Marketing"),
    ("Real Estate", "CRM Implementation"),
    # Clinics
    ("Clinics",     "CRM Implementation"),
    ("Clinics",     "AI Automation"),
    # Gyms
    ("Gyms",        "Website Development"),
    ("Gyms",        "Digital Marketing"),
    # Salons
    ("Salons",      "SEO Services"),
    ("Salons",      "Digital Marketing"),
    # Hotels
    ("Hotels",      "SEO Services"),
    ("Hotels",      "Website Development"),
    # Schools
    ("Schools",     "CRM Implementation"),
    ("Schools",     "Website Development"),
]

# ── Realistic business name banks per industry ─────────────────────────────────
NAME_BANKS = {
    "Hospitals": [
        "CarePlus", "MediLife", "HealthVibe", "CityMed", "SunCare",
        "LifeLine", "MedFirst", "HealWell", "Fortify", "TrueCare",
        "PrimeMed", "GlobalCare", "SevaCare", "ApexHealth", "UrbanMed",
        "NovaCare", "PeopleMed", "ShreeMed", "BrightHealth", "MedicoPlus",
        "RajHealth", "ShivHealth", "SurgiCare", "DiagnoPlus", "WellCure",
    ],
    "Restaurants": [
        "SpiceCraft", "TandoorHouse", "ZaiqaKitchen", "RoyalDhaba",
        "SaffronEats", "CurryLeaf", "FlavorHub", "TastyTales", "ChaiPoint",
        "BiryaniBowl", "MasalaMagic", "FoodCourt", "HungerFix", "YumYard",
        "PlateFull", "SpiceBox", "UrbanChef", "FoodStreet", "BhojanAlaya",
        "GoldenFork", "GrillHouse", "SeasonedBites", "TiffinWala", "EatRight",
        "KitchenCo",
    ],
    "Real Estate": [
        "PrimeNest", "UrbanSpaces", "ElevateRealty", "LandmarkProp",
        "SkylarkHomes", "NexusRealty", "BuildRight", "DreamDwell",
        "GoldenKey", "SpaceCraft", "CityHomes", "PremierBuilders",
        "TrustProp", "VistaProp", "NestWell", "PropertiesPlus",
        "HomeFront", "RealWorth", "InfraBuild", "ClassicHomes",
        "FutureBuild", "EliteEstates", "HomeCraft", "BuildNest", "VantageRealty",
    ],
    "Clinics": [
        "WellCare", "MedicoLife", "QuickHeal", "FamilyCare", "PulseCare",
        "SmileDental", "VisionPlus", "SkinGlow", "OrthoCare", "HealthFirst",
        "HealQuick", "ClinicPlus", "MedPoint", "CureWell", "DiagnoLife",
        "BodyCare", "TreatWell", "SpecialistPlus", "CliniqCare", "UrgentCare",
        "PrimeCare", "MediHouse", "TotalCure", "AllWell", "DocCare",
    ],
    "Gyms": [
        "UrbanFit", "PeakZone", "IronForce", "FitNation", "PulseFit",
        "PowerHouse", "MaxFit", "EliteFitness", "StrongBox", "CoreZone",
        "LiftZone", "FitLife", "BodyPeak", "ProFit", "GainZone",
        "FitSquare", "AthleteCo", "MuscleMate", "FitHub", "SweatBox",
        "ActiveZone", "FitForce", "HealthZone", "FitSpace", "FlexFit",
    ],
    "Salons": [
        "BellaGlow", "GlamourStudio", "TrendSetters", "StyleVibe",
        "HairCraft", "LookBook", "ChicStudio", "GlowUp", "SnipStyle",
        "MirrorMirror", "BlushBar", "SalonElite", "TressPlus", "GlamZone",
        "CurlStudio", "RootsTip", "BeautyNook", "StyleStation", "ShineOn",
        "SilkHair", "SalonVogue", "PrettyPlus", "AllureStyle", "LushLooks",
        "PolishPro",
    ],
    "Hotels": [
        "ComfortInn", "RoyalStay", "MetroSuites", "StayPrime", "TravelNest",
        "CityGrand", "EliteInn", "CozyCourt", "UrbanStay", "NightCap",
        "HotelPeak", "PrimeRooms", "LuxeStay", "OakHotel", "GreenLeaf",
        "BlueSky", "SilverKey", "HarborView", "PlazaInn", "StarlightHotel",
        "SpringHotel", "HeritageInn", "CrystalHotel", "GrandPalace", "SunriseHotel",
    ],
    "Schools": [
        "BrightMinds", "EduCraft", "FutureLeaders", "LearnRight",
        "AcademyCrest", "KnowledgeHub", "ScholarPeak", "WisdomTree",
        "BrightStar", "LittleGenius", "GrowthAcademy", "LearnWell",
        "EduFirst", "ThinkBig", "SkyHigh", "MindSpark", "ProdigySchool",
        "TalentHub", "ExcelAcademy", "RiseSchool", "StepAhead", "TopMind",
        "SmartKids", "BrainBox", "PathwaySchool",
    ],
}

SOURCES = ["Google Maps", "JustDial", "Sulekha", "IndiaMart", "Facebook Pages", "LinkedIn"]

# ── AI recommendations per service ────────────────────────────────────────────
AI_REC = {
    "Website Development": [
        "Outdated website detected — losing potential clients to modern competitors.",
        "No mobile-responsive website found, missing 70% of mobile traffic.",
        "Website loading speed is critically slow — affecting bounce rate.",
        "No online booking or contact form detected on current website.",
        "Website design is 5+ years old — needs a modern UI overhaul.",
    ],
    "SEO Services": [
        "Missing SEO optimization — not ranking in local Google searches.",
        "Google My Business listing incomplete — losing local discovery.",
        "Zero backlink profile detected — very low domain authority.",
        "No keyword strategy found — competitors outranking for key terms.",
        "Low Google visibility score — paid ads needed alongside SEO.",
    ],
    "Digital Marketing": [
        "No active Google Ads campaigns — missing high-intent customers.",
        "Social media accounts inactive for 3+ months — audience decay.",
        "Low online review count — weak trust signals for new customers.",
        "No retargeting campaigns — losing warm leads to competitors.",
        "Brand awareness very low in target city — needs awareness push.",
    ],
    "CRM Implementation": [
        "No CRM system found — leads likely managed on spreadsheets.",
        "Missing follow-up automation — warm leads going cold.",
        "No customer retention workflow — high churn probability.",
        "Sales team tracking manually — inefficient and error-prone.",
        "Zero lead nurturing sequence detected — revenue leakage identified.",
    ],
    "AI Automation": [
        "Manual intake and scheduling process — automation can save 15 hrs/week.",
        "No chatbot or AI response system — slow customer response times.",
        "Repetitive admin tasks identified — AI can handle 60% of current workload.",
        "No predictive analytics in place — business decisions are reactive.",
        "Customer communication is unautomated — missing upsell opportunities.",
    ],
}

PAIN_SIGNALS = {
    "Website Development": "website_is_outdated",
    "SEO Services":        "no_google_maps_listing",
    "Digital Marketing":   "last_social_post_old",
    "CRM Implementation":  "negative_reviews_found",
    "AI Automation":       "website_not_mobile",
}

BUDGET_MAP = {
    "Hospitals":   ["₹2L–₹5L", "> ₹5L"],
    "Restaurants": ["₹25k–₹1L", "₹1L–₹2L"],
    "Real Estate": ["₹1L–₹5L", "> ₹5L"],
    "Clinics":     ["₹50k–₹2L", "₹2L–₹5L"],
    "Gyms":        ["₹25k–₹1L", "₹1L–₹2L"],
    "Salons":      ["< ₹25k", "₹25k–₹1L"],
    "Hotels":      ["₹1L–₹5L", "> ₹5L"],
    "Schools":     ["₹50k–₹2L", "₹2L–₹5L"],
}

DOMAIN_SUFFIXES = [".com", ".in", ".co.in"]

# ── Generators ────────────────────────────────────────────────────────────────

def _phone():
    return f"+91-{random.choice([70,72,73,74,75,76,78,79,80,81,82,83,84,85,86,87,88,90,91,92,93,94,95,96,97,98,99])}{random.randint(10000000,99999999)}"

def _email(slug):
    prefixes = ["info", "contact", "hello", "team", "admin", "sales", "enquiry"]
    return f"{random.choice(prefixes)}@{slug}{random.choice(DOMAIN_SUFFIXES)}"

def _website(slug):
    return f"http://www.{slug}{random.choice(DOMAIN_SUFFIXES)}"

def _slug(name):
    return name.lower().replace(" ", "").replace("&", "and")[:20]

def _last_active(tier):
    if tier == "HOT":
        days_ago = random.randint(1, 4)
    elif tier == "WARM":
        days_ago = random.randint(5, 21)
    else:
        days_ago = random.randint(30, 90)
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

def _score(tier):
    if tier == "HOT":  return random.randint(90, 98)
    if tier == "WARM": return random.randint(75, 89)
    return random.randint(60, 74)

def _label(score):
    if score >= 85: return "HOT"
    if score >= 70: return "WARM"
    return "COLD"

def _growth(score):
    if score >= 90: return "High"
    if score >= 75: return "Medium"
    return "Low"

def _quality(score):
    if score >= 90: return "Premium"
    if score >= 75: return "Good"
    return "Fair"

def make_lead(name_base, city, industry, service, tier, idx):
    city_abbr = city.replace(" ", "").replace("NCR","")[:3].title()
    suffix_num = f"{idx+1:02d}"
    company = f"{name_base} {city_abbr}{suffix_num}"

    slug  = _slug(company)
    score = _score(tier)

    has_website = tier == "HOT" or (tier == "WARM" and random.random() > 0.3) or (tier == "COLD" and random.random() > 0.7)
    has_phone   = tier == "HOT" or (tier == "WARM" and random.random() > 0.25) or (tier == "COLD" and random.random() > 0.6)
    has_email   = tier == "HOT" or (tier == "WARM" and random.random() > 0.35) or (tier == "COLD" and random.random() > 0.65)

    website = _website(slug) if has_website else ""
    phone   = _phone()       if has_phone   else ""
    email   = _email(slug)   if has_email   else ""

    ai_rec = random.choice(AI_REC[service])
    pain   = PAIN_SIGNALS[service]

    budget = random.choice(BUDGET_MAP.get(industry, ["₹25k–₹1L", "₹1L–₹5L"]))

    return {
        "company_name":      company,
        "city":              city,
        "category":          service,   # stored in `industry` column
        "source":            random.choice(SOURCES),
        "phone":             phone,
        "email":             email,
        "website":           website,
        "website_alive":     has_website,
        "fit_score":         random.randint(60, 95),
        "intent_score":      score,
        "contact_score":     90 if (has_phone and has_email) else (70 if (has_phone or has_email) else 30),
        "composite_score":   float(score),
        "label":             _label(score),
        "pain_point":        ai_rec,
        "hot_reason":        ai_rec,
        "decision_maker":    random.choice(["Owner", "Director", "Founder", "CEO", "Manager", "Partner"]),
        "buying_signals":    json.dumps(["Active search signals", "Budget confirmed", "Decision maker reachable"] if tier == "HOT"
                                        else ["Potential interest", "Website traffic spike"] if tier == "WARM"
                                        else ["Passive presence only"]),
        "objection_1":       "Budget is tight this quarter",
        "rebuttal_1":        "We offer milestone-based billing with clear ROI benchmarks.",
        "objection_2":       "We already have someone handling this",
        "rebuttal_2":        "We provide a free audit showing exactly what's being missed.",
        "best_channel":      "WhatsApp" if has_phone else ("Email" if has_email else "LinkedIn"),
        "personalized_opener": f"Hi, we noticed {company} in {city} could benefit from {service} — {ai_rec[:60]}",
        "whatsapp_msg":      f"Hi {company} team! We help {industry} businesses in {city} with {service}. Can we share a quick insight specific to your business?",
        "linkedin_msg":      f"Hello! We work with {industry} businesses in {city} on {service}. Would love to connect and share what's working right now.",
        "email_subject":     f"{service} opportunity for {company}",
        "email_msg":         f"Hi,\n\n{ai_rec}\n\nWe've helped {industry} businesses in {city} solve this exact problem with {service}.\n\nWould you be open to a 15-min call this week?\n\nBest,\nClientFinder Team",
        "review_status":     "approved",
        "status":            "New",
        "description":       f"{industry} business in {city} needing {service}. Tier: {tier}. Budget: {budget}. Last active: {_last_active(tier)}.",
        "pain_signals_json": json.dumps({
            "negative_reviews_found": pain == "negative_reviews_found" or random.random() > 0.7,
            "website_is_outdated":    pain == "website_is_outdated" or not has_website,
            "no_google_maps_listing": pain == "no_google_maps_listing" or random.random() > 0.5,
            "website_not_mobile":     pain == "website_not_mobile" or not has_website,
            "last_social_post_old":   pain == "last_social_post_old" or random.random() > 0.4,
        }),
        # Extra demo enrichment fields
        "growth_potential":  _growth(score),
        "lead_quality":      _quality(score),
        "ai_recommendation": ai_rec,
        "budget_range":      budget,
        "industry_tag":      industry,
        "lead_tier":         tier,
        "last_active":       _last_active(tier),
    }


def run():
    print("Clearing existing leads...")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM leads")
    try:
        conn.execute("DELETE FROM sqlite_sequence WHERE name='leads'")
    except Exception:
        pass
    conn.commit()
    conn.close()

    create_tables()

    total = 0
    seen  = set()

    for city in CITIES:
        for industry, service in VALID_COMBOS:
            names = NAME_BANKS[industry].copy()
            random.shuffle(names)
            name_iter = iter(names * 5)   # repeat bank to ensure enough names

            # HOT: 3-5 leads
            hot_count = random.randint(3, 5)
            for i in range(hot_count):
                base = next(name_iter)
                lead = make_lead(base, city, industry, service, "HOT", i)
                key  = (lead["company_name"], city, service)
                if key in seen: continue
                seen.add(key)
                try:
                    save_lead(lead)
                    total += 1
                except Exception:
                    pass

            # WARM: 8-15 leads
            warm_count = random.randint(8, 15)
            for i in range(warm_count):
                base = next(name_iter)
                lead = make_lead(base, city, industry, service, "WARM", hot_count + i)
                key  = (lead["company_name"], city, service)
                if key in seen: continue
                seen.add(key)
                try:
                    save_lead(lead)
                    total += 1
                except Exception:
                    pass

            # COLD: 15-25 leads
            cold_count = random.randint(15, 25)
            for i in range(cold_count):
                base = next(name_iter)
                lead = make_lead(base, city, industry, service, "COLD", hot_count + warm_count + i)
                key  = (lead["company_name"], city, service)
                if key in seen: continue
                seen.add(key)
                try:
                    save_lead(lead)
                    total += 1
                except Exception:
                    pass

    print(f"Done! {total} leads inserted.")
    print(f"Cities: {len(CITIES)} | Combos: {len(VALID_COMBOS)} | Total per city: ~{total//len(CITIES)}")

if __name__ == "__main__":
    run()
