"""Shared fixtures. Written from docs/contract.md only; no application code is
imported at module level so collection works before the code exists."""
import hashlib
import hmac
import json
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # pytest's default import mode puts tests/ on sys.path, not the repo root.
    sys.path.insert(0, str(ROOT))

ALDER = "alderbrook-law"
FERN = "fernwick-llp"
ALDER_INBOX = "dockets@alderbrook-law.example"
FERN_INBOX = "dockets@fernwick-llp.example"
SECRETS = {ALDER: "alderbrook-fixture-key", FERN: "fernwick-fixture-key"}

# Contract section 8: exact bytes, no trailing newline.
EXAMPLE_BODY = (
    b'{"notice_id":"NTC-8841","inbox":"dockets@alderbrook-law.example",'
    b'"text":"Notice of filing. Matter ID: M-3108. Order on scheduling entered. '
    b'Filed 2026-10-29. This is an automated notice; do not reply."}'
)
EXAMPLE_SIG = "4c741de4b7c0ab97653176ed0e3c6476e4f5a4142fe23295626f4c747d9523f2"
EXAMPLE_TEXT = (
    "Notice of filing. Matter ID: M-3108. Order on scheduling entered. "
    "Filed 2026-10-29. This is an automated notice; do not reply."
)


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def body_for(notice_id: str, inbox: str, text: str) -> bytes:
    return json.dumps({"notice_id": notice_id, "inbox": inbox, "text": text}).encode()


def query(db_path, sql, params=()):
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


class RecordingExtractor:
    """Fake extractor: records every call. `answer` is a value or a callable(text)."""

    def __init__(self, answer, delay: float = 0.0):
        self._answer = answer
        self._delay = delay
        self._lock = threading.Lock()
        self.calls = []

    def __call__(self, text):
        with self._lock:
            self.calls.append(text)
        if self._delay:
            import time

            time.sleep(self._delay)
        if callable(self._answer):
            return self._answer(text)
        return self._answer


def raising_extractor(text):
    raise RuntimeError("extractor exploded")


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "litigence.db"
    monkeypatch.setenv("LITIGENCE_DB", str(path))
    return str(path)


@pytest.fixture
def db(db_path):
    """Initialised and seeded temp database; returns its path."""
    from app.db import connect, init_db

    conn = connect(db_path)
    try:
        init_db(conn)
        conn.commit()
    finally:
        conn.close()
    return db_path


@pytest.fixture
def conn(db):
    from app.db import connect

    c = connect(db)
    yield c
    c.close()


@pytest.fixture
def app(db):
    from app.main import create_app

    return create_app(db)


@pytest.fixture
def make_client(app):
    """Factory for independent TestClients on the same app/db (for concurrency)."""
    from fastapi.testclient import TestClient

    opened = []

    def _make():
        c = TestClient(app)
        c.__enter__()
        opened.append(c)
        return c

    yield _make
    for c in opened:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def post_notice(client):
    """post_notice(body_bytes, signature=None|str) -> response."""

    def _post(body: bytes, signature=None, c=None):
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers["X-Signature"] = signature
        return (c or client).post("/webhooks/notices", content=body, headers=headers)

    return _post


@pytest.fixture
def add_notice(db):
    """Insert a notice row directly (bypasses intake). Returns its integer id."""

    def _add(tenant_id, notice_id, text="Notice text.", status="received",
             matter_id=None, filing_type=None, filed_date=None, needs_review=0):
        c = sqlite3.connect(db, timeout=10)
        try:
            cur = c.execute(
                "INSERT INTO notices (tenant_id, notice_id, text, status, matter_id,"
                " filing_type, filed_date, needs_review) VALUES (?,?,?,?,?,?,?,?)",
                (tenant_id, notice_id, text, status, matter_id, filing_type,
                 filed_date, needs_review),
            )
            c.commit()
            return cur.lastrowid
        finally:
            c.close()

    return _add


@pytest.fixture
def rows(db):
    """rows(sql, params=()) -> list of dicts, read with a fresh sqlite3 connection."""

    def _rows(sql, params=()):
        return query(db, sql, params)

    return _rows


def run_concurrently(fns):
    """Run callables in threads released together by a barrier; return results in order.
    Any exception is re-raised in the caller."""
    barrier = threading.Barrier(len(fns))
    results = [None] * len(fns)
    errors = []

    def runner(i, fn):
        try:
            barrier.wait(timeout=10)
            results[i] = fn()
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=runner, args=(i, f)) for i, f in enumerate(fns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads), "concurrent call hung"
    if errors:
        raise errors[0]
    return results


@pytest.fixture
def concurrently():
    return run_concurrently
