import sqlite3

import pytest

from tests.support import ALDER, FERN, INVALID, TEXT, VALID
from worker.checks import check, run_extraction


BAD_ANSWERS = [
    None, [], "order", 1, True, {},
    {"filing_type": "order", "matter_id": "M-3108"},
    {"filing_type": "order", "filed_date": None},
    {"matter_id": "M-3108", "filed_date": None},
    *[dict(VALID, filing_type=value) for value in [None, "ORDER", "appeal", "", 1, [], {}]],
    *[dict(VALID, matter_id=value) for value in [0, False, [], {}, "", "M-9999", "M-4410"]],
    *[dict(VALID, filed_date=value) for value in [
        0, False, [], {}, "", "2026-02-29", "2026-04-31", "2026-13-01", "2026-00-01",
        "0000-01-01", "2026-01-00", "2026-1-01", "20261029", "2026-W44-4",
        "2026-10-29T00:00:00", " 2026-10-29", "2026-10-29\n",
    ]],
]


@pytest.mark.parametrize("answer", BAD_ANSWERS)
def test_bad_answer_nulls_all_fields(conn, answer):
    assert check(answer, ALDER, conn) == INVALID


@pytest.mark.parametrize("filing_type", ["complaint", "motion", "order", "other"])
@pytest.mark.parametrize("date", [None, "2024-02-29", "2000-02-29", "2026-10-29"])
def test_all_valid_types_and_nullable_dates(conn, filing_type, date):
    answer = dict(VALID, filing_type=filing_type, filed_date=date)
    assert check(answer, ALDER, conn) == dict(answer, needs_review=False)


def test_no_matter_is_valid_but_needs_review(conn):
    answer = dict(VALID, matter_id=None)
    assert check(answer, ALDER, conn) == dict(answer, needs_review=True)


@pytest.mark.parametrize("tenant", [ALDER, FERN])
def test_shared_matter_is_valid_for_each_tenant(conn, tenant):
    assert check(VALID, tenant, conn) == dict(VALID, needs_review=False)


@pytest.mark.parametrize("tenant,matter", [(ALDER, "M-4410"), (FERN, "M-3109")])
def test_other_tenant_exclusive_matter_is_rejected(conn, tenant, matter):
    assert check(dict(VALID, matter_id=matter), tenant, conn) == INVALID


@pytest.mark.parametrize("error", [RuntimeError("extract failed"), sqlite3.OperationalError("extractor fault")])
def test_extractor_exception_is_invalid_answer(conn, error):
    def broken(text):
        raise error
    assert run_extraction(TEXT, ALDER, conn, extractor=broken) == INVALID


def test_extractor_receives_only_original_text(conn):
    calls = []
    def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return dict(VALID)
    assert run_extraction(TEXT, ALDER, conn, extractor=fake) == dict(VALID, needs_review=False)
    assert calls == [((TEXT,), {})]


def test_database_lookup_error_propagates(conn):
    conn.execute("DROP TABLE matters")
    with pytest.raises(sqlite3.Error):
        check(VALID, ALDER, conn)
    with pytest.raises(sqlite3.Error):
        run_extraction(TEXT, ALDER, conn, extractor=lambda text: dict(VALID))
