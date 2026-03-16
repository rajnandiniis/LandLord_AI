"""
utils/validator.py
==================
All input validation and edge case checks.
Returns (is_valid: bool, error_message: str)
"""

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png"}
MAX_FILE_MB = 10
MIN_TEXT_LENGTH = 50


def check_api_key(key: str) -> tuple[bool, str]:
    if not key:
        return False, "No API key entered. Add your OpenAI key in the sidebar."
    if not key.startswith("sk-"):
        return False, "Invalid API key format. Key must start with 'sk-'."
    if len(key) < 20:
        return False, "API key too short. Check you copied it correctly."
    return True, ""


def check_file(file) -> tuple[bool, str]:
    if file is None:
        return False, "No file uploaded."
    name = file.name.lower()
    ext = "." + name.split(".")[-1]
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{ext}' not supported. Use PDF, DOCX, TXT, JPG, or PNG."
    size_mb = file.size / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        return False, f"File too large ({size_mb:.1f} MB). Maximum is {MAX_FILE_MB} MB."
    if file.size == 0:
        return False, "File appears to be empty. Please try a different file."
    return True, ""


def check_text(text: str) -> tuple[bool, str]:
    if not text or not text.strip():
        return False, "No text could be extracted from this file. Try pasting text manually."
    if len(text.strip()) < MIN_TEXT_LENGTH:
        return False, f"Extracted text is too short ({len(text.strip())} chars). Document may be blank or unreadable."
    return True, ""


def check_manual_text(text: str) -> tuple[bool, str]:
    if not text or not text.strip():
        return False, "Please upload a file or paste violation text."
    if len(text.strip()) < 20:
        return False, "Text too short. Please paste the full violation notice."
    return True, ""


def sanitize_filename(name: str) -> str:
    """Make a string safe to use as a filename."""
    import re
    name = str(name or "unknown")
    name = re.sub(r'[^\w\s\-]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name[:50] or "unknown"
