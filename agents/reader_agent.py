"""
agents/reader_agent.py
======================
Agent 1 — Reads and parses a violation notice into structured data.
"""

import json
from config.settings import load_prompt

_PROMPT = load_prompt("reader_prompt.txt")


def analyze_violation(text: str, client) -> dict:
    """
    Takes raw violation text, returns structured dict with all violation details.
    Falls back to safe defaults if parsing fails.
    """
    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user",   "content": f"Analyze this NYC violation notice:\n\n{text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            timeout=45,
        )
        return json.loads(r.choices[0].message.content)
    except json.JSONDecodeError:
        return _fallback("JSON parse failed")
    except Exception as e:
        return _fallback(str(e))


def _fallback(reason: str) -> dict:
    return {
        "error": True,
        "error_reason": reason,
        "agency": "Unknown",
        "violation_class": "Unknown",
        "violation_type": "Could not parse violation",
        "severity": "HIGH",
        "what_happened": "Unable to automatically parse. Please review the document manually.",
        "immediate_risk": "Unknown — treat as urgent until clarified.",
        "response_deadline_days": 30,
        "fine_per_day": "Unknown",
        "total_potential_fine": "Unknown",
        "can_appeal": True,
        "appeal_success_rate": "N/A",
        "hearing_date": "N/A",
        "case_number": "N/A",
        "property_address": "N/A",
    }
