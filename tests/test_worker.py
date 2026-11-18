"""Worker and shared check (contract sections 4-6, brief Part B)."""
import os
import subprocess
import sys

import pytest

from conftest import ALDER, FERN, ROOT, RecordingExtractor, raising_extractor

NULLS = {"matter_id": None, "filing_type": None, "filed_date": None}


def good(matter="M-3108", ftype="order", date="2026-10-29"):
    return {"filing_type": ftype, "matter_id": matter, "filed_date": date}


def assert_invalid(result):
    assert result["matter_id"] is None
    assert result["filing_type"] is None
    assert result["filed_date"] is None
    assert bool(result["needs_review"]) is True


# ------------------------------------------------------------- check table

VALID_CASES = [
    # (tenant, answer, expected needs_review)
    (ALDER, good(), False),
    (ALDER, good(matter="M-3109", ftype="motion"), False),
    (FERN, good(matter="M-4410", ftype="complaint"), False),
    (FERN, good(matter="M-3108", ftype="other"), False),
    (ALDER, good(date=None), False),                  # null date is valid
    (ALDER, good(matter=None), True),                 # valid, no matter -> review
    (ALDER, good(matter=None, date=None), True),
    (ALDER, good(date="2028-02-29"), False),          # real leap day
]


@pytest.mark.parametrize("tenant,answer,review", VALID_CASES)
def test_check_valid_answers(conn, tenant, answer, review):
    from worker.checks import check

    result = check(dict(answer), tenant, conn)
    assert result["matter_id"] == answer["matter_id"]
    assert result["filing_type"] == answer["filing_type"]
    assert result["filed_date"] == answer["filed_date"]
    assert bool(result["needs_review"]) is review


BAD_SHAPES = [
    None,
    "order",
    42,
    ["order", "M-3108", "2026-10-29"],
    ("order", "M-3108", "2026-10-29"),
    {},
    {"matter_id": "M-3108", "filed_date": "2026-10-29"},              # no filing_type
    {"filing_type": "order", "filed_date": "2026-10-29"},             # no matter_id
    {"filing_type": "order", "matter_id": "M-3108"},                  # no filed_date
    good(ftype="appeal"),                                             # unknown type
    good(ftype=None),
    good(ftype=7),
    good(ftype="Order"),                                              # not exactly in set
    good(matter=3108),
    good(matter=["M-3108"]),
    good(matter="M-9999"),                                            # nobody's matter
    good(matter="M-4410"),                                            # fernwick only
    good(matter="m-3108"),
    good(date="2026-02-30"),                                          # impossible date
    good(date="2026-02-29"),                                          # not a leap year
    good(date="2026-13-01"),
    good(date="2026-00-10"),
    good(date="29/10/2026"),
    good(date="2026-10-29T00:00:00"),
    good(date="20261029"),                                            # basic ISO, not YYYY-MM-DD
    good(date="2026-1-5"),
    good(date=""),
    good(date=20261029),
]


@pytest.mark.parametrize("answer", BAD_SHAPES, ids=[f"bad{i}" for i in range(len(BAD_SHAPES))])
def test_check_invalid_answers_are_all_null_and_need_review(conn, answer):
    from worker.checks import check

    result = check(answer, ALDER, conn)
    assert_invalid(result)


def test_check_returns_exactly_the_four_keys(conn):
    from worker.checks import check

    assert set(check(good(), ALDER, conn)) == {
        "matter_id", "filing_type", "filed_date", "needs_review"}
    assert set(check(None, ALDER, conn)) == {
        "matter_id", "filing_type", "filed_date", "needs_review"}


def test_check_cross_tenant_matter_is_invalid_both_ways(conn):
    from worker.checks import check

    assert_invalid(check(good(matter="M-4410"), ALDER, conn))   # fernwick only
    assert_invalid(check(good(matter="M-3109"), FERN, conn))    # alderbrook only


def test_check_m3108_valid_in_both_tenants(conn):
    from worker.checks import check

    for tenant in (ALDER, FERN):
        result = check(good(matter="M-3108"), tenant, conn)
        assert result["matter_id"] == "M-3108"
        assert bool(result["needs_review"]) is False


def test_run_extraction_raising_extractor_is_invalid_not_raised(conn):
    from worker.checks import run_extraction

    assert_invalid(run_extraction("Matter ID: M-3108.", ALDER, conn, extractor=raising_extractor))


def test_run_extraction_passes_text_only(conn):
    from worker.checks import run_extraction

    seen = []

    def fake(*args, **kwargs):
        seen.append((args, kwargs))
        return good()

    result = run_extraction("the notice text", ALDER, conn, extractor=fake)
    assert seen == [(("the notice text",), {})]
    assert result["matter_id"] == "M-3108"


# --------------------------------------------------------------- run_once


def test_run_once_processes_received_to_pending(db, add_notice, rows):
    from worker.run import run_once

    add_notice(ALDER, "N-1", text="alpha")
    add_notice(FERN, "N-2", text="beta")
    fake = RecordingExtractor(lambda t: good() if t == "alpha" else good(matter="M-4410"))
    assert run_once(db, extractor=fake) == 2
    assert sorted(fake.calls) == ["alpha", "beta"]
    got = rows("SELECT tenant_id, notice_id, status, matter_id, filing_type, filed_date,"
               " needs_review FROM notices ORDER BY id")
    assert got == [
        {"tenant_id": ALDER, "notice_id": "N-1", "status": "pending", "matter_id": "M-3108",
         "filing_type": "order", "filed_date": "2026-10-29", "needs_review": 0},
        {"tenant_id": FERN, "notice_id": "N-2", "status": "pending", "matter_id": "M-4410",
         "filing_type": "order", "filed_date": "2026-10-29", "needs_review": 0},
    ]
    # Nothing left: a second run processes nothing and does not call the extractor.
    assert run_once(db, extractor=fake) == 0
    assert len(fake.calls) == 2


def test_run_once_uses_env_db_when_no_path(db, add_notice, rows):
    from worker.run import run_once

    add_notice(ALDER, "N-1")
    assert run_once(extractor=RecordingExtractor(good())) == 1   # LITIGENCE_DB set by fixture
    assert rows("SELECT status FROM notices") == [{"status": "pending"}]


def test_run_once_skips_non_received(db, add_notice, rows):
    from worker.run import run_once

    add_notice(ALDER, "P", status="pending", matter_id="M-3108", filing_type="order")
    add_notice(ALDER, "D", status="docketed", matter_id="M-3108", filing_type="order")
    add_notice(ALDER, "X", status="processing")
    fake = RecordingExtractor(good())
    assert run_once(db, extractor=fake) == 0
    assert fake.calls == []


def test_extractor_receives_notice_text_only(db, add_notice):
    from worker.run import run_once

    seen = []

    def fake(*args, **kwargs):
        seen.append((args, kwargs))
        return good()

    add_notice(ALDER, "N-1", text="Matter ID: M-3108. Order. Filed 2026-10-29.")
    assert run_once(db, extractor=fake) == 1
    assert seen == [(("Matter ID: M-3108. Order. Filed 2026-10-29.",), {})]


@pytest.mark.parametrize("tenant,matter", [(FERN, "M-3109"), (ALDER, "M-4410")])
def test_worker_matter_only_in_other_tenant_three_nulls(db, add_notice, rows, tenant, matter):
    from worker.run import run_once

    add_notice(tenant, "N-1", text=f"Matter ID: {matter}. Motion. Filed 2026-11-02.")
    assert run_once(db, extractor=RecordingExtractor(good(matter=matter, ftype="motion",
                                                          date="2026-11-02"))) == 1
    assert rows("SELECT status, matter_id, filing_type, filed_date, needs_review FROM notices") == [
        {"status": "pending", "matter_id": None, "filing_type": None, "filed_date": None,
         "needs_review": 1}
    ]


def test_worker_m3108_resolves_per_tenant(db, add_notice, rows):
    from worker.run import run_once

    add_notice(ALDER, "A-1", text="alder M-3108")
    add_notice(FERN, "F-1", text="fern M-3108")
    assert run_once(db, extractor=RecordingExtractor(good(matter="M-3108"))) == 2
    got = rows("SELECT tenant_id, matter_id, needs_review, status FROM notices ORDER BY tenant_id")
    assert got == [
        {"tenant_id": ALDER, "matter_id": "M-3108", "needs_review": 0, "status": "pending"},
        {"tenant_id": FERN, "matter_id": "M-3108", "needs_review": 0, "status": "pending"},
    ]


def test_worker_valid_answer_without_matter_needs_review(db, add_notice, rows):
    from worker.run import run_once

    add_notice(ALDER, "N-1")
    assert run_once(db, extractor=RecordingExtractor(good(matter=None))) == 1
    assert rows("SELECT status, matter_id, filing_type, filed_date, needs_review FROM notices") == [
        {"status": "pending", "matter_id": None, "filing_type": "order",
         "filed_date": "2026-10-29", "needs_review": 1}
    ]


@pytest.mark.parametrize("answer", BAD_SHAPES, ids=[f"bad{i}" for i in range(len(BAD_SHAPES))])
def test_worker_bad_extractor_answer_stored_null_pending(db, add_notice, rows, answer):
    from worker.run import run_once

    add_notice(ALDER, "N-1")
    assert run_once(db, extractor=RecordingExtractor(answer)) == 1
    assert rows("SELECT status, matter_id, filing_type, filed_date, needs_review FROM notices") == [
        {"status": "pending", "needs_review": 1, **NULLS}
    ]


def test_worker_raising_extractor_does_not_stop_the_run(db, add_notice, rows):
    from worker.run import run_once

    add_notice(ALDER, "boom", text="boom")
    add_notice(ALDER, "fine", text="fine")

    def flaky(text):
        if text == "boom":
            raise ValueError("bad")
        return good()

    assert run_once(db, extractor=flaky) == 2
    got = rows("SELECT notice_id, status, matter_id, needs_review FROM notices ORDER BY id")
    assert got == [
        {"notice_id": "boom", "status": "pending", "matter_id": None, "needs_review": 1},
        {"notice_id": "fine", "status": "pending", "matter_id": "M-3108", "needs_review": 0},
    ]


# ------------------------------------- database errors propagate (amended 4, 6)

DB_ERROR = "synthetic disk I/O failure"


@pytest.fixture
def broken_matter_lookup(monkeypatch):
    """Make app.db.matter_ids raise sqlite3.OperationalError. Also patches a name
    imported directly into worker.checks, so the test does not depend on how
    checks binds it (contract: checks uses app.db.matter_ids)."""
    import sqlite3

    import app.db
    import worker.checks

    calls = []

    def boom(conn, tenant_id):
        calls.append(tenant_id)
        raise sqlite3.OperationalError(DB_ERROR)

    monkeypatch.setattr(app.db, "matter_ids", boom)
    if hasattr(worker.checks, "matter_ids"):
        monkeypatch.setattr(worker.checks, "matter_ids", boom)
    return calls


@pytest.mark.parametrize("tenant,matter", [(ALDER, "M-3108"), (FERN, "M-4410"),
                                           (ALDER, "M-4410"), (ALDER, "M-9999")])
def test_check_db_error_in_matter_lookup_propagates(conn, broken_matter_lookup, tenant, matter):
    import sqlite3

    from worker.checks import check

    # A well-formed answer whose matter must be looked up: the lookup failure is
    # a database error, not an invalid answer.
    with pytest.raises(sqlite3.Error):
        check(good(matter=matter), tenant, conn)
    assert broken_matter_lookup, "check did not use app.db.matter_ids"


def test_run_extraction_db_error_propagates_not_treated_as_extractor_error(
        conn, broken_matter_lookup):
    import sqlite3

    from worker.checks import run_extraction

    with pytest.raises(sqlite3.Error):
        run_extraction("Matter ID: M-3108.", ALDER, conn,
                       extractor=RecordingExtractor(good(matter="M-3108")))


def test_check_bad_answers_never_raise_on_healthy_db(conn):
    from worker.checks import check

    weird = [
        good(matter={"M-3108": 1}),      # unhashable matter_id
        good(matter={"M-3108"}),
        good(ftype=["order"]),            # unhashable filing_type
        good(date=["2026-10-29"]),
        good(date=b"2026-10-29"),
        good(matter=b"M-3108"),
        object(),
    ]
    for answer in BAD_SHAPES + weird:
        try:
            result = check(answer, ALDER, conn)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"check raised {e!r} for bad answer {answer!r}")
        assert_invalid(result)


def test_run_once_db_error_raises_and_leaves_notice_processing(db, add_notice, rows,
                                                               broken_matter_lookup):
    import sqlite3

    from worker.run import run_once

    add_notice(ALDER, "N-1", text="Matter ID: M-3108. Order. Filed 2026-10-29.")
    add_notice(ALDER, "N-2", text="second")
    fake = RecordingExtractor(good(matter="M-3108"))
    with pytest.raises(sqlite3.Error):
        run_once(db, extractor=fake)
    got = rows("SELECT notice_id, status, matter_id, filing_type, filed_date, needs_review"
               " FROM notices ORDER BY id")
    # First notice: claimed, nothing written (not stored as an invalid answer).
    assert got[0] == {"notice_id": "N-1", "status": "processing", "matter_id": None,
                      "filing_type": None, "filed_date": None, "needs_review": 0}
    # Processing stops: the second notice is never claimed.
    assert got[1] == {"notice_id": "N-2", "status": "received", "matter_id": None,
                      "filing_type": None, "filed_date": None, "needs_review": 0}
    assert fake.calls == ["Matter ID: M-3108. Order. Filed 2026-10-29."]


def test_run_once_db_error_reported_on_stderr(db, add_notice, capsys, broken_matter_lookup):
    import sqlite3

    from worker.run import run_once

    add_notice(ALDER, "N-1")
    with pytest.raises(sqlite3.Error):
        run_once(db, extractor=RecordingExtractor(good(matter="M-3108")))
    assert DB_ERROR in capsys.readouterr().err


# --------------------------------------------------------- two workers at once


@pytest.mark.parametrize("workers", [2, 4])
def test_concurrent_run_once_processes_each_notice_once(db, add_notice, rows, concurrently,
                                                        workers):
    from worker.run import run_once

    n = 40
    for i in range(n):
        add_notice(ALDER if i % 2 else FERN, f"N-{i}", text=f"text-{i}")
    fake = RecordingExtractor(good(matter="M-3108"), delay=0.005)
    counts = concurrently([lambda: run_once(db, extractor=fake) for _ in range(workers)])
    assert sum(counts) == n, counts
    assert sorted(fake.calls) == sorted(f"text-{i}" for i in range(n)), "a notice was extracted twice or skipped"
    assert rows("SELECT COUNT(*) AS n FROM notices WHERE status='pending'") == [{"n": n}]


def test_two_worker_processes_at_once_process_each_notice_once(db, add_notice, rows):
    """`python -m worker --once` twice at the same moment, real extractor."""
    n = 30
    for i in range(n):
        add_notice(ALDER, f"N-{i}",
                   text=f"Notice of filing. Matter ID: M-3108. Order entered. Filed 2026-10-{i % 28 + 1:02d}.")
    env = dict(os.environ, LITIGENCE_DB=db)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    procs = [
        subprocess.Popen([sys.executable, "-m", "worker", "--once"], cwd=str(ROOT), env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    outs = [p.communicate(timeout=60) for p in procs]
    for p, (out, err) in zip(procs, outs):
        assert p.returncode == 0, err
    totals = []
    for out, _ in outs:
        last = out.strip().splitlines()[-1]
        word, num = last.split()
        assert word == "processed"
        totals.append(int(num))
    assert sum(totals) == n, totals
    assert rows("SELECT COUNT(*) AS n FROM notices WHERE status='pending'") == [{"n": n}]
