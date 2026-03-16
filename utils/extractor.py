"""
utils/extractor.py
==================
Extracts plain text from PDF, DOCX, TXT, and images.
No Streamlit imports — pure utility functions.
"""

import base64
import tempfile
import os


def extract_from_pdf(file) -> str:
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        file.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(file.read())
            tmp = f.name
        text = pdfminer_extract(tmp)
        os.unlink(tmp)
        return text or ""
    except Exception as e:
        raise RuntimeError(f"PDF read error: {e}")


def extract_from_docx(file) -> str:
    try:
        from docx import Document
        file.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as f:
            f.write(file.read())
            tmp = f.name
        doc = Document(tmp)
        os.unlink(tmp)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        raise RuntimeError(f"DOCX read error: {e}")


def extract_from_txt(file) -> str:
    try:
        file.seek(0)
        return file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        raise RuntimeError(f"TXT read error: {e}")


def extract_from_image(file, client) -> str:
    """Use GPT-4o Vision to extract text from image."""
    try:
        file.seek(0)
        data = base64.b64encode(file.read()).decode()
        ext = file.name.split(".")[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        r = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                {"type": "text", "text": (
                    "Extract ALL text from this NYC legal/property violation notice. "
                    "Include every word, number, date, code, and reference number exactly as printed."
                )}
            ]}],
            max_tokens=2000,
            timeout=30,
        )
        return r.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"Image OCR error: {e}")


def extract_text(file, client=None) -> str:
    """
    Master extractor — routes to correct method based on file type.
    Pass client only if image support needed.
    """
    name = file.name.lower()
    if name.endswith(".pdf"):
        return extract_from_pdf(file)
    elif name.endswith(".docx"):
        return extract_from_docx(file)
    elif name.endswith(".txt"):
        return extract_from_txt(file)
    elif name.endswith((".jpg", ".jpeg", ".png")):
        if client is None:
            raise RuntimeError("OpenAI client required for image extraction.")
        return extract_from_image(file, client)
    else:
        raise RuntimeError(f"Unsupported file type: {name}")


def fetch_violations_from_api(address: str) -> list:
    import requests

    HPD_URL = "https://data.cityofnewyork.us/resource/wvxf-dwi5.json"

    # ── Parse street name only — ignore house number ──────────────────────
    parts = address.strip().upper().split()

    # Drop leading house number
    if parts and parts[0].replace("-", "").isdigit():
        parts = parts[1:]

    # Drop trailing borough
    borough_words = {"MANHATTAN", "BROOKLYN", "BRONX", "QUEENS", "STATEN", "ISLAND"}
    while parts and parts[-1] in borough_words:
        parts.pop()

    street_name = " ".join(parts)  # e.g. "STAGG STREET"

    if not street_name:
        raise RuntimeError("Could not parse street name from address.")

    try:
        params = {
            "$where": f"violationstatus='Open' AND streetname='{street_name}'",
            "$order": "inspectiondate DESC",
            "$limit": 20,
        }
        r = requests.get(HPD_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        results = []
        for v in data:
            v["_source"] = "HPD"
            results.append(v)
        return results

    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot reach NYC database. Check your internet connection.")
    except requests.exceptions.Timeout:
        raise RuntimeError("NYC database timed out. Try again.")
    except Exception as e:
        raise RuntimeError(f"API error: {e}")

def format_violation_text(v: dict) -> str:
    """
    Convert a raw HPD API violation dict into clean text
    that the AI agents can read and analyze properly.
    """
    lines = [
        "NYC HPD VIOLATION NOTICE",
        "=" * 40,
        f"Violation ID:    {v.get('violationid', 'N/A')}",
        f"Building ID:     {v.get('buildingid', 'N/A')}",
        f"Borough:         {v.get('boro', 'N/A')}",
        f"Address:         {v.get('housenumber', '')} {v.get('streetname', '')}",
        f"Apartment:       {v.get('apartment', 'N/A')}",
        f"Floor/Story:     {v.get('story', 'N/A')}",
        f"ZIP Code:        {v.get('zip', 'N/A')}",
        "",
        f"VIOLATION CLASS: {v.get('class', 'N/A')}",
        f"Order Number:    {v.get('ordernumber', 'N/A')}",
        f"NOV ID:          {v.get('novid', 'N/A')}",
        "",
        f"VIOLATION DESCRIPTION:",
        f"{v.get('novdescription', 'N/A')}",
        "",
        f"Inspection Date:       {v.get('inspectiondate', 'N/A')[:10] if v.get('inspectiondate') else 'N/A'}",
        f"NOV Issued Date:       {v.get('novissueddate', 'N/A')[:10] if v.get('novissueddate') else 'N/A'}",
        f"Original Correct By:   {v.get('originalcorrectbydate', 'N/A')[:10] if v.get('originalcorrectbydate') else 'N/A'}",
        f"Original Certify By:   {v.get('originalcertifybydate', 'N/A')[:10] if v.get('originalcertifybydate') else 'N/A'}",
        "",
        f"CURRENT STATUS:  {v.get('currentstatus', 'N/A')}",
        f"Status Date:     {v.get('currentstatusdate', 'N/A')[:10] if v.get('currentstatusdate') else 'N/A'}",
        f"Violation Status:{v.get('violationstatus', 'N/A')}",
        f"Rent Impairing:  {v.get('rentimpairing', 'N/A')}",
    ]
    return "\n".join(lines)
