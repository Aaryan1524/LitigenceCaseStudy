"""Deterministic notice extractor. Rules follow contract section 9.

Text inside a notice is data only; nothing in it alters these patterns.
"""

import re

_MATTER_RE = re.compile(r"Matter ID: (M-\d{4})")
_FILED_RE = re.compile(r"Filed (\d{4}-\d{2}-\d{2})")
_TYPE_RE = re.compile(r"\b(complaint|motion|order)\b", re.IGNORECASE)


def extract(text: str) -> dict:
    """Return filing_type, matter_id and filed_date parsed from notice text."""
    matter_match = _MATTER_RE.search(text)
    filed_match = _FILED_RE.search(text)
    type_match = _TYPE_RE.search(text)

    return {
        "filing_type": type_match.group(1).lower() if type_match else "other",
        "matter_id": matter_match.group(1) if matter_match else None,
        "filed_date": filed_match.group(1) if filed_match else None,
    }
