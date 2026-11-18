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
    """Validate an extractor answer for one tenant.

    Never raises for a bad answer. A sqlite3.Error from the matter lookup is a
    database problem, not an answer problem, so it propagates (contract 4, 6).
    """
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
        if matter_id is not None and not isinstance(matter_id, str):
            return _invalid()
        if filed_date is not None:
            if not isinstance(filed_date, str) or not _real_date(filed_date):
                return _invalid()
    except Exception:
        return _invalid()

    # Outside the blanket except: a database error here must propagate.
    if matter_id is not None:
        known = matter_ids(conn, tenant_id)
        try:
            if matter_id not in known:
                return _invalid()
        except Exception:
            return _invalid()

    return {
        "matter_id": matter_id,
        "filing_type": filing_type,
        "filed_date": filed_date,
        "needs_review": matter_id is None,
    }


def run_extraction(text: str, tenant_id: str, conn, extractor: Extractor = extract) -> dict:
    """check(extractor(text), tenant_id, conn).

    An extractor exception is an invalid answer; a sqlite3.Error from check's
    matter lookup propagates to the caller.
    """
    try:
        answer = extractor(text)
    except Exception:
        return _invalid()
    return check(answer, tenant_id, conn)
