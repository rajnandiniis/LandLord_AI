"""
config/settings.py
==================
All app-wide constants, violation data, and prompt loader.
Nothing here touches Streamlit or OpenAI directly.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

APP_NAME    = "LandlordAI"
APP_SUB     = "NYC Property Violation Assistant"
APP_VERSION = "2.0"

# ── Violation class reference data ───────────────────────────────────────────
VIOLATION_CLASSES = {
    "Class A (Non-Hazardous)": {
        "deadline_days": 90,
        "severity": "low",
        "fine_range": "$10 – $50/day",
        "description": "Non-hazardous — cosmetic or minor maintenance issues",
        "color": "#059669",
    },
    "Class B (Hazardous)": {
        "deadline_days": 30,
        "severity": "medium",
        "fine_range": "$25 – $100/day",
        "description": "Hazardous — may affect tenant health or safety",
        "color": "#d97706",
    },
    "Class C (Immediately Hazardous)": {
        "deadline_days": 1,
        "severity": "critical",
        "fine_range": "$50 – $250/day",
        "description": "Immediately dangerous — no heat, gas leaks, vermin",
        "color": "#dc2626",
    },
    "Class I (DOB — Immediately Dangerous)": {
        "deadline_days": 1,
        "severity": "critical",
        "fine_range": "$1,000 – $25,000",
        "description": "Structural danger — must cease occupancy",
        "color": "#dc2626",
    },
}

# ── NYC Agency reference ──────────────────────────────────────────────────────
NYC_AGENCIES = [
    ("HPD", "Housing Preservation & Development", "Residential building violations", "212-863-5620"),
    ("DOB", "Department of Buildings",            "Construction, permits, structural", "212-393-2550"),
    ("ECB", "Environmental Control Board",        "Civil penalties, hearings",         "212-933-3000"),
    ("OATH","Office of Admin Trials & Hearings",  "Where you fight violations",        "212-933-3000"),
    ("FDNY","Fire Department NYC",                "Fire code, sprinkler, alarms",      "718-999-2000"),
    ("DEP", "Environmental Protection",           "Water, sewer, environmental",       "718-595-7000"),
]

# ── Fine reduction playbook ───────────────────────────────────────────────────
FINE_REDUCTION_TIPS = [
    ("Fix it fast",           "Correct before hearing → judge often dismisses fine entirely"),
    ("File Cert of Correction","Official proof of fix → strongest evidence in hearing"),
    ("Show good faith",       "Repair receipts + invoices = fine reduction up to 50%"),
    ("First-time offense",    "No prior violations = significant leniency from OATH judges"),
    ("Claim obstruction",     "Document tenant's refused access with certified letters"),
    ("Request adjournment",   "Buy time to gather evidence and fix the issue"),
]

# ── Document types for summons generator ─────────────────────────────────────
SUMMONS_TYPES = [
    "14-Day Rent Demand Notice",
    "Notice to Cure (Lease Violation)",
    "Notice to Quit (Before Eviction)",
    "OATH Hearing Response Letter",
    "Repair Access Request to Tenant",
    "Security Deposit Demand Letter",
]

# ── Prompt loader ─────────────────────────────────────────────────────────────
def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

def load_template(filename: str) -> str:
    path = TEMPLATES_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""
