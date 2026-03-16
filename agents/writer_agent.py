"""
agents/writer_agent.py
======================
Agent 3 — Writes formal response and appeal letters.
"""

import json
from datetime import datetime
from config.settings import load_prompt

_PROMPT = load_prompt("writer_prompt.txt")


def write_letters(vdata: dict, rdata: dict, owner_name: str, client) -> dict:
    """
    Takes violation + research data, returns response letter, appeal letter, cert notes.
    """
    ctx = f"""
Property Owner / LLC: {owner_name}
Violation: {vdata.get('violation_type')}
Case Number: {vdata.get('case_number')}
Address: {vdata.get('property_address')}
Agency: {vdata.get('agency')}
Fine: {vdata.get('fine_per_day')}
Recommendation: {rdata.get('recommendation')}
Key defenses: {', '.join(rdata.get('landlord_defenses', [])[:2])}
Today: {datetime.now().strftime('%B %d, %Y')}
"""
    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user",   "content": f"Write letters for this NYC violation:\n{ctx}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=45,
        )
        return json.loads(r.choices[0].message.content)
    except Exception as e:
        return {
            "error": True,
            "response_letter": f"Error generating letter: {e}\n\nPlease try again or contact support.",
            "appeal_letter": "",
            "correction_certificate_notes": "",
            "send_to_address": "",
            "send_method": "",
            "key_arguments": [],
        }
