"""
ClaudeFlow Stage 1 exception handler: missing-field recovery.
When a document's completeness score is low, Claude attempts to extract
the missing fields directly from the raw document text.
"""

import json
import logging
from claudeflow.claude_classifier import _get_client

log = logging.getLogger("claudeflow.field_filler")

_FILL_SYSTEM = """
You are a contract completeness recovery agent for ClaudeFlow.
A document classifier found missing required fields. Your job:
examine the raw document text and attempt to extract or infer
the missing field values. Return ONLY valid JSON where each key
is a missing field name and the value is the extracted text
(or null if genuinely not found).

Be conservative: only return a value you can directly evidence
from the text. Do not invent. If a field is truly absent, set null.
"""


def fill_missing_fields(
    document_text: str,
    missing_fields: list[str],
    filename: str = "",
) -> dict[str, str | None]:
    """
    Ask Claude to recover missing fields from raw document text.
    Returns a dict of {field_name: extracted_value_or_null}.
    """
    if not missing_fields:
        return {}

    field_list = "\n".join(f"- {f}" for f in missing_fields)
    prompt = (
        f"Filename: {filename}\n\n"
        f"Missing fields to find:\n{field_list}\n\n"
        f"Document text (first 3000 chars):\n{document_text[:3000]}\n\n"
        f"Return JSON: {{\"field_name\": \"extracted value or null\", ...}}"
    )

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=_FILL_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    try:
        recovered = json.loads(raw)
        log.info("field_filler recovered %d/%d fields", sum(1 for v in recovered.values() if v), len(missing_fields))
        return recovered
    except json.JSONDecodeError:
        log.warning("field_filler: invalid JSON from Claude, returning empty")
        return {f: None for f in missing_fields}


def compute_recovery_score(original_score: int, recovered: dict[str, str | None]) -> int:
    """Recompute completeness after recovery. Each recovered field adds up to 5 points, capped at 100."""
    filled = sum(1 for v in recovered.values() if v is not None)
    bonus = min(filled * 5, 30)
    return min(original_score + bonus, 100)
