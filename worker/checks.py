"""The ONE validation path shared by the worker and evals (contract sections 4 and 5)."""
import datetime
import re
from typing import Callable

from app.constants import FILING_TYPES
from app.db import matter_ids
from extractor import extract

Extractor = Callable[[str], object]

KEYS = ("filing_type", "matter_id", "filed_date")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _invalid() -> dict:
    return {"matter_id": None, "filing_type": None, "filed_date": None, "needs_review": True}


def _real_date(value: str) -> bool:
    if not _DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def check(answer: object, tenant_id: str, conn) -> dict:
    """Validate an extractor answer for one tenant. Never raises."""
    try:
        if not isinstance(answer, dict):
            return _invalid()
        if any(k not in answer for k in KEYS):
            return _invalid()
        filing_type = answer["filing_type"]
        matter_id = answer["matter_id"]
        filed_date = answer["filed_date"]
        if not isinstance(filing_type, str) or filing_type not in FILING_TYPES:
            return _invalid()
        if matter_id is not None:
            if not isinstance(matter_id, str) or matter_id not in matter_ids(conn, tenant_id):
                return _invalid()
        if filed_date is not None:
            if not isinstance(filed_date, str) or not _real_date(filed_date):
                return _invalid()
        return {
            "matter_id": matter_id,
            "filing_type": filing_type,
            "filed_date": filed_date,
            "needs_review": matter_id is None,
        }
    except Exception:
        return _invalid()


def run_extraction(text: str, tenant_id: str, conn, extractor: Extractor = extract) -> dict:
    """check(extractor(text), tenant_id, conn); an extractor exception is an invalid answer."""
    try:
        answer = extractor(text)
    except Exception:
        return _invalid()
    return check(answer, tenant_id, conn)
