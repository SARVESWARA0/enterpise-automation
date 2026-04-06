"""
Document Processor — Uses LOCAL Ollama (llama3) to extract metadata from
PDFs and images. All processing is done on-device; no document content
ever leaves the machine or enters the agent orchestration pipeline.

Supports: Aadhaar, PAN, Passport, Driving License, and generic documents.

Architecture:
  1. PyPDF2 extracts raw text from PDF  (or PIL EXIF for images)
  2. Text is sent to LOCAL Ollama llama3 for structured extraction
  3. Extracted metadata is validated against employee record
  4. Only the structured metadata (JSON) is stored in DB
  5. Raw text is NEVER persisted or forwarded to the workflow engine
"""
import re
import os
import json
import uuid
import httpx
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# ── Ollama Configuration ─────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
_ENV_MODEL = os.getenv("OLLAMA_DOC_MODEL", "llama3")  # Dedicated env var for doc processing


def _resolve_ollama_model() -> str:
    """
    Determine which Ollama model to use. Checks what's actually installed
    and picks the best available model for document extraction.
    """
    preferred = _ENV_MODEL
    try:
        r = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        installed = [m["name"].split(":")[0] for m in r.json().get("models", [])]
        # Exact match (without :tag)
        if preferred.split(":")[0] in installed:
            return preferred
        # Try common fallbacks
        for fallback in ["llama3", "llama3.1", "llama3.2", "mistral", "phi3"]:
            if fallback in installed:
                return fallback
        # Use whatever is available
        if installed:
            return installed[0]
    except Exception:
        pass
    return preferred


OLLAMA_MODEL = _resolve_ollama_model()
print(f"[DocProcessor] Ollama: {OLLAMA_HOST} | Model: {OLLAMA_MODEL}")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1: RAW TEXT EXTRACTION (no LLM needed)
# ══════════════════════════════════════════════════════════════════════════════

def extract_text_from_pdf(filepath: str) -> str:
    """Extract all text content from a PDF file using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        print(f"[DocProcessor] PDF extraction error: {e}")
        return ""


def extract_text_from_image(filepath: str) -> str:
    """
    Extract text from image via PIL EXIF + filename heuristics.
    For full OCR you'd integrate pytesseract — here we do best-effort.
    """
    text_parts = []
    basename = os.path.splitext(os.path.basename(filepath))[0]
    cleaned_name = re.sub(r'[_\-]+', ' ', basename)
    text_parts.append(cleaned_name)

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        img = Image.open(filepath)
        exif_data = img._getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if isinstance(value, str):
                    text_parts.append(f"{tag}: {value}")
    except Exception:
        pass

    return "\n".join(text_parts)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2: LOCAL OLLAMA LLM EXTRACTION  (llama3, fully on-device)
# ══════════════════════════════════════════════════════════════════════════════

_EXTRACTION_PROMPT = """You are a document metadata extraction assistant. You MUST respond with ONLY valid JSON, no other text.

Analyze the following document text and extract structured metadata. The document is an Indian identity/government document (could be Aadhaar, PAN card, Passport, Driving License, Voter ID, or other).

Extract the following fields where available:
- "document_type": the type of document (e.g. "Aadhaar Card", "PAN Card", "Passport", "Driving License", "Voter ID", "Other")
- "document_category": one of "aadhaar", "pan", "passport", "driving_license", "voter_id", "other"
- "name": full name of the person
- "date_of_birth": DOB in the format found in document
- "gender": Male/Female/Transgender
- "document_number": the ID number (Aadhaar number, PAN number, Passport number, etc.)
- "fathers_name": father's name if present
- "address": full address if present
- "nationality": nationality if present
- "place_of_issue": place of issue if present
- "email": email if present
- "phone": phone number if present
- "additional_info": any other relevant metadata as a string

Rules:
1. Return ONLY a JSON object, no markdown, no explanation, no extra text
2. Use null for fields you cannot find
3. For Aadhaar, the number is 12 digits (often in groups of 4)
4. For PAN, the format is ABCDE1234F (5 letters, 4 digits, 1 letter)
5. For Passport, the format is a letter followed by 7 digits
6. Be accurate — do not guess or fabricate data

DOCUMENT TEXT:
---
{text}
---

JSON:"""


def _call_ollama(prompt: str, timeout: float = 60.0) -> str:
    """Call local Ollama API. Returns raw response text."""
    try:
        response = httpx.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,      # Low temp for deterministic extraction
                    "num_predict": 1024,      # Enough for a JSON response
                    "top_p": 0.9,
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
    except httpx.ConnectError:
        print(f"[DocProcessor] ERROR: Cannot connect to Ollama at {OLLAMA_HOST}. Is it running?")
        return ""
    except Exception as e:
        print(f"[DocProcessor] Ollama call failed: {e}")
        return ""


def _parse_llm_json(raw_response: str) -> dict:
    """
    Parse JSON from LLM response, handling common issues like markdown fences,
    trailing text, etc.
    """
    text = raw_response.strip()
    if not text:
        return {}

    # Remove markdown code fences if present
    if text.startswith("```"):
        # Strip ```json or ``` prefix and trailing ```
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```\s*$', '', text)

    # Try to find JSON object in the response
    # Find the first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Last resort: try parsing entire text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"[DocProcessor] Could not parse LLM response as JSON: {text[:200]}")
        return {}


def extract_with_ollama(raw_text: str) -> dict:
    """
    Send extracted text to LOCAL Ollama llama3 for structured extraction.
    Returns a dict of extracted fields. Never sends data externally.
    """
    if not raw_text or not raw_text.strip():
        return {"document_type": "Unknown", "document_category": "other"}

    # Truncate very long texts to keep LLM focused
    truncated = raw_text[:4000] if len(raw_text) > 4000 else raw_text

    prompt = _EXTRACTION_PROMPT.format(text=truncated)

    print(f"[DocProcessor] Calling Ollama ({OLLAMA_MODEL}) for extraction...")
    raw_response = _call_ollama(prompt)

    if not raw_response:
        print("[DocProcessor] Ollama returned empty response, falling back to regex")
        return {}

    parsed = _parse_llm_json(raw_response)

    # Clean up null values
    cleaned = {}
    for key, value in parsed.items():
        if value is not None and value != "" and value != "null":
            cleaned[key] = value

    print(f"[DocProcessor] Ollama extracted {len(cleaned)} fields")
    return cleaned


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2B: REGEX FALLBACK (when Ollama is unavailable)
# ══════════════════════════════════════════════════════════════════════════════

def _detect_category_regex(text: str, filename: str) -> str:
    """Detect document type from text content and filename (no LLM)."""
    combined = (text + " " + filename).lower()
    if any(k in combined for k in ["aadhaar", "aadhar", "uid", "uidai", "unique identification"]):
        return "aadhaar"
    if any(k in combined for k in ["permanent account number", "pan card", "income tax"]):
        return "pan"
    if re.search(r'\bpan\b', combined) and re.search(r'[A-Z]{5}[0-9]{4}[A-Z]', text):
        return "pan"
    if any(k in combined for k in ["passport", "republic of india", "nationality", "date of issue"]):
        return "passport"
    if any(k in combined for k in ["driving licence", "driving license", "dl no", "transport"]):
        return "driving_license"
    if any(k in combined for k in ["voter", "election commission", "epic"]):
        return "voter_id"
    return "other"


def _extract_fields_regex(text: str, category: str) -> dict:
    """Regex-based field extraction as fallback when Ollama is unavailable."""
    fields = {}

    # Name
    name_match = re.search(r'(?:name|naam)\s*[:\-]?\s*([A-Za-z ]{3,40})', text, re.IGNORECASE)
    if name_match:
        fields["name"] = name_match.group(1).strip()

    # DOB
    dob_match = re.search(
        r'(?:DOB|Date of Birth|d\.?o\.?b\.?|birth)\s*[:\-]?\s*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
        text, re.IGNORECASE
    )
    if dob_match:
        fields["date_of_birth"] = dob_match.group(1)

    # Gender
    gender_match = re.search(r'\b(male|female|transgender)\b', text, re.IGNORECASE)
    if gender_match:
        fields["gender"] = gender_match.group(1).capitalize()

    # Document numbers by category
    if category == "aadhaar":
        m = re.search(r'\b(\d{4}\s?\d{4}\s?\d{4})\b', text)
        if m:
            fields["document_number"] = re.sub(r'\s', '', m.group(1))
        fields["document_type"] = "Aadhaar Card"
    elif category == "pan":
        m = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b', text)
        if m:
            fields["document_number"] = m.group(1)
        fields["document_type"] = "PAN Card"
        father = re.search(r"(?:father|father's name)\s*[:\-]?\s*([A-Za-z ]{3,40})", text, re.IGNORECASE)
        if father:
            fields["fathers_name"] = father.group(1).strip()
    elif category == "passport":
        m = re.search(r'\b([A-Z]\d{7})\b', text)
        if m:
            fields["document_number"] = m.group(1)
        fields["document_type"] = "Passport"
        nat = re.search(r'(?:nationality|country)\s*[:\-]?\s*([A-Za-z ]{3,20})', text, re.IGNORECASE)
        if nat:
            fields["nationality"] = nat.group(1).strip()
    else:
        fields["document_type"] = "Other Document"

    # Address
    addr_match = re.search(r'(?:address|addr)\s*[:\-]?\s*(.{10,120})', text, re.IGNORECASE)
    if addr_match:
        fields["address"] = addr_match.group(1).strip()

    # Email
    email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', text)
    if email_match:
        fields["email"] = email_match.group(0)

    return fields


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3: MAIN EXTRACTION PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def extract_metadata(filepath: str, file_type: str, original_name: str = "") -> dict:
    """
    Main extraction entry point.

    Pipeline:
      1. Extract raw text from PDF/image (PyPDF2 / PIL)
      2. Send text to LOCAL Ollama llama3 for structured extraction
      3. Fall back to regex if Ollama is unavailable
      4. Return structured metadata (raw text is NEVER stored)

    Returns: {
        "category": "aadhaar|pan|passport|...",
        "extraction_method": "ollama_llama3" | "regex_fallback",
        "fields": { "name": ..., "document_number": ..., ... }
    }
    """
    # Step 1: Extract raw text
    if file_type in ("application/pdf", "pdf"):
        raw_text = extract_text_from_pdf(filepath)
    else:
        raw_text = extract_text_from_image(filepath)

    has_text = bool(raw_text and raw_text.strip())
    extraction_method = "none"
    fields = {}
    category = "other"

    if has_text:
        # Step 2: Try Ollama extraction first
        ollama_result = extract_with_ollama(raw_text)

        if ollama_result and len(ollama_result) > 1:
            # Ollama succeeded — use its output
            extraction_method = f"ollama_{OLLAMA_MODEL}"
            category = ollama_result.pop("document_category", "other")
            fields = ollama_result
            print(f"[DocProcessor] ✓ Ollama extraction successful: {category}")
        else:
            # Step 3: Fallback to regex
            extraction_method = "regex_fallback"
            category = _detect_category_regex(raw_text, original_name)
            fields = _extract_fields_regex(raw_text, category)
            print(f"[DocProcessor] ⚠ Regex fallback used: {category}")
    else:
        # No text at all — try category from filename
        category = _detect_category_regex("", original_name)
        fields = {"document_type": category.replace("_", " ").title()}
        extraction_method = "filename_only"
        print(f"[DocProcessor] ⚠ No text content, using filename: {category}")

    # IMPORTANT: raw_text is NOT included in the return value
    # This ensures document content never enters the DB or agent pipeline
    return {
        "category": category,
        "extraction_method": extraction_method,
        "raw_text_length": len(raw_text) if raw_text else 0,
        "has_text_content": has_text,
        "fields": fields,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4: VALIDATION (compares extracted fields to employee record)
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip, collapse whitespace."""
    if not name:
        return ""
    return re.sub(r'\s+', ' ', name.strip().lower())


def _name_similarity(name_a: str, name_b: str) -> float:
    """
    Name similarity score (0.0 to 1.0).
    Handles: exact match, case insensitivity, word reordering, partial matches.
    """
    a = _normalize_name(name_a)
    b = _normalize_name(name_b)

    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85

    parts_a = set(a.split())
    parts_b = set(b.split())
    if not parts_a or not parts_b:
        return 0.0
    if parts_a == parts_b:
        return 0.95

    common = parts_a & parts_b
    total = parts_a | parts_b
    if common:
        return round(len(common) / len(total), 2)
    return 0.0


def validate_against_employee(extracted_data: dict, employee: dict) -> dict:
    """
    Validate extracted document fields against the employee record.
    Only structured metadata is compared — raw document text is never used.

    Returns: {
        "status": "valid" | "invalid" | "partial" | "pending",
        "score": 0.0 - 1.0,
        "extraction_method": "ollama_llama3" | "regex_fallback",
        "fields": { ... per-field validation details ... }
    }
    """
    fields = extracted_data.get("fields", {})
    extraction_method = extracted_data.get("extraction_method", "unknown")
    validation_fields = {}
    match_count = 0
    total_checks = 0

    # ── Name validation ──
    extracted_name = fields.get("name", "")
    employee_name = employee.get("name", "")
    if extracted_name:
        total_checks += 1
        similarity = _name_similarity(extracted_name, employee_name)
        is_match = similarity >= 0.6
        if is_match:
            match_count += 1
        validation_fields["name"] = {
            "extracted": extracted_name,
            "expected": employee_name,
            "match": is_match,
            "similarity": similarity,
        }

    # ── Email validation ──
    extracted_email = fields.get("email", "")
    employee_email = employee.get("email", "")
    if extracted_email:
        total_checks += 1
        is_match = extracted_email.lower().strip() == employee_email.lower().strip()
        if is_match:
            match_count += 1
        validation_fields["email"] = {
            "extracted": extracted_email,
            "expected": employee_email,
            "match": is_match,
        }

    # ── Document number (record only, no comparison) ──
    doc_num = fields.get("document_number", "")
    if doc_num:
        validation_fields["document_number"] = {
            "extracted": doc_num,
            "expected": None,
            "match": None,
            "note": "Recorded for reference",
        }

    # ── DOB (record only) ──
    dob = fields.get("date_of_birth", "")
    if dob:
        validation_fields["date_of_birth"] = {
            "extracted": dob,
            "expected": None,
            "match": None,
            "note": "Recorded for reference",
        }

    # ── Gender (record only) ──
    gender = fields.get("gender", "")
    if gender:
        validation_fields["gender"] = {
            "extracted": gender,
            "expected": None,
            "match": None,
        }

    # ── Address (record only) ──
    address = fields.get("address", "")
    if address:
        validation_fields["address"] = {
            "extracted": address,
            "expected": None,
            "match": None,
        }

    # ── Father's name (record only) ──
    fathers_name = fields.get("fathers_name", "")
    if fathers_name:
        validation_fields["fathers_name"] = {
            "extracted": fathers_name,
            "expected": None,
            "match": None,
        }

    # Determine overall status
    if total_checks == 0:
        status = "pending"
        score = 0.0
    elif match_count == total_checks:
        status = "valid"
        score = 1.0
    elif match_count > 0:
        status = "partial"
        score = round(match_count / total_checks, 2)
    else:
        status = "invalid"
        score = 0.0

    return {
        "status": status,
        "score": score,
        "extraction_method": extraction_method,
        "checks_performed": total_checks,
        "checks_passed": match_count,
        "fields": validation_fields,
    }
