"""
agents/document_agent.py
========================
Agent 4 — Scrapes structured data from any document + generates summons text.
"""

import json
from datetime import datetime
from config.settings import load_prompt, load_template

_DOC_PROMPT = load_prompt("document_prompt.txt")

# Extract only the SCRAPER_ROLE section
_SCRAPER_PROMPT = ""
_SUMMONS_PROMPT = ""
if _DOC_PROMPT:
    if "SCRAPER_ROLE:" in _DOC_PROMPT and "SUMMONS_ROLE:" in _DOC_PROMPT:
        parts = _DOC_PROMPT.split("SUMMONS_ROLE:")
        _SCRAPER_PROMPT = parts[0].replace("SCRAPER_ROLE:", "").strip()
        _SUMMONS_PROMPT = parts[1].strip()


def scrape_document(text: str, client) -> dict:
    """Extract all structured data from any property-related document."""
    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _SCRAPER_PROMPT},
                {"role": "user",   "content": f"Extract all data from this document:\n\n{text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            timeout=45,
        )
        data = json.loads(r.choices[0].message.content)
        data["extracted_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        return data
    except Exception as e:
        return {
            "error": True,
            "error_reason": str(e),
            "issue_summary": "Extraction failed — please try again.",
            "urgency": "HIGH",
            "summons_applicable": False,
            "extracted_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


def generate_summons_text(rec: dict, doc_type: str, owner_name: str, client) -> str:
    """
    Uses AI to generate a fully filled summons/notice letter.
    Falls back to template if AI fails.
    """
    today_str = datetime.now().strftime("%B %d, %Y")

    # Try to format amount
    raw_amount = rec.get("total_overdue") or rec.get("amount_owed") or "0"
    try:
        amount_fmt = f"${float(str(raw_amount).replace(',', '').replace('$', '') or 0):,.2f}"
    except Exception:
        amount_fmt = f"${raw_amount}"

    user_msg = f"""Draft a {doc_type} with this exact data:

Tenant: {rec.get('tenant_name', '[TENANT NAME]')}
Unit: {rec.get('tenant_unit', '[UNIT]')}
Property: {rec.get('tenant_address', '[ADDRESS]')} {rec.get('tenant_city','')} {rec.get('tenant_state','')} {rec.get('tenant_zip','')}
Landlord/Owner: {owner_name or rec.get('landlord_name', '[OWNER]')}
Amount Owed: {amount_fmt}
Monthly Rent: ${rec.get('monthly_rent', '[RENT]')}
Months Overdue: {rec.get('months_overdue', '[MONTHS]')}
Lease Start: {rec.get('lease_start', '[DATE]')}
Deadline: {rec.get('deadline_date', '[DATE]')}
Issue Summary: {rec.get('issue_summary', '')}
Today's Date: {today_str}
Case Number: {rec.get('case_number', 'N/A')}

Write the complete {doc_type} now."""

    try:
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _SUMMONS_PROMPT},
                {"role": "user",   "content": user_msg}
            ],
            temperature=0.15,
            max_tokens=1400,
            timeout=45,
        )
        return r.choices[0].message.content
    except Exception:
        # Fall back to template
        return _fill_template(doc_type, rec, owner_name, today_str, amount_fmt)


def _fill_template(doc_type: str, rec: dict, owner_name: str, today: str, amount: str) -> str:
    """Fill a legal template with record data as fallback."""
    tpl_map = {
        "14-Day Rent Demand Notice":      "rent_demand.txt",
        "Notice to Cure (Lease Violation)":"notice_to_cure.txt",
        "Notice to Quit (Before Eviction)":"eviction_notice.txt",
        "OATH Hearing Response Letter":    "summons_draft.txt",
        "Repair Access Request to Tenant": "rent_demand.txt",
        "Security Deposit Demand Letter":  "rent_demand.txt",
    }
    tpl = load_template(tpl_map.get(doc_type, "rent_demand.txt"))
    if not tpl:
        return f"[{doc_type}]\n\nTenant: {rec.get('tenant_name')}\nAmount: {amount}\nDate: {today}"

    replacements = {
        "[DATE]":           today,
        "[TENANT_NAME]":    rec.get("tenant_name", "[TENANT NAME]"),
        "[TENANT_UNIT]":    str(rec.get("tenant_unit", "")),
        "[TENANT_ADDRESS]": rec.get("tenant_address", ""),
        "[TENANT_CITY]":    rec.get("tenant_city", ""),
        "[TENANT_STATE]":   rec.get("tenant_state", "NY"),
        "[TENANT_ZIP]":     str(rec.get("tenant_zip", "")),
        "[LANDLORD_NAME]":  owner_name or rec.get("landlord_name", "[OWNER]"),
        "[LANDLORD_ADDRESS]": rec.get("landlord_address", ""),
        "[PROPERTY_ADDRESS]": rec.get("property_address") or rec.get("tenant_address", ""),
        "[MONTHLY_RENT]":   str(rec.get("monthly_rent", "")),
        "[MONTHS_OVERDUE]": str(rec.get("months_overdue", "")),
        "[TOTAL_OVERDUE]":  amount,
        "[AMOUNT_OWED]":    amount,
        "[LEASE_START]":    str(rec.get("lease_start", "")),
        "[LEASE_END]":      str(rec.get("lease_end", "")),
        "[DEADLINE_DATE]":  str(rec.get("deadline_date", "")),
        "[HEARING_DATE]":   str(rec.get("hearing_date", "")),
        "[CASE_NUMBER]":    str(rec.get("case_number", "N/A")),
        "[ISSUE_SUMMARY]":  rec.get("issue_summary", ""),
        "[COUNTY]":         "Kings" if "brooklyn" in str(rec.get("tenant_city","")).lower() else "New York",
        "[COURT_ADDRESS]":  "141 Livingston Street, Brooklyn, NY 11201",
    }
    for k, v in replacements.items():
        tpl = tpl.replace(k, str(v) if v else k)
    return tpl
