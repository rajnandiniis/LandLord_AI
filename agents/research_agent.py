"""
agents/research_agent.py
========================
Agent 2 — Researches NYC law and builds optimal action plan.
"""

import json
from config.settings import load_prompt

_PROMPT = load_prompt("research_prompt.txt")


def build_action_plan(vdata: dict, client) -> dict:
    """
    Takes violation data dict, returns action plan with steps, defenses, tips.
    """
    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user",   "content": f"Build action plan for this NYC violation:\n{json.dumps(vdata, indent=2)}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
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
        "recommendation": "CONSULT LAWYER",
        "recommendation_reason": "Could not generate automated strategy. Please consult a licensed NYC attorney.",
        "confidence": 0.0,
        "action_steps": [
            {
                "step": 1,
                "priority": "URGENT",
                "deadline": "Immediately",
                "action": "Contact a licensed NYC property attorney",
                "how_to": "Call NYC Bar Referral at 212-626-7373 for a free referral.",
                "cost_estimate": "Free consultation available"
            }
        ],
        "fine_reduction_strategies": [],
        "landlord_defenses": [],
        "documents_to_gather": [],
        "free_resources": ["NYC Bar Lawyer Referral: 212-626-7373", "Legal Aid Society: 212-577-3300"],
        "worst_case_if_ignored": "Default judgment, escalating fines, possible property lien.",
        "best_case_if_handled_correctly": "Violation dismissed with proper documentation.",
    }
