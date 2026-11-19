"""Synthetic fixtures and independent request signing, from the contract."""
import hashlib
import hmac
import json

from app.db import connect

ALDER = "alderbrook-law"
FERN = "fernwick-llp"
INBOXES = {
    ALDER: "dockets@alderbrook-law.example",
    FERN: "dockets@fernwick-llp.example",
}
SECRETS = {ALDER: b"alderbrook-fixture-key", FERN: b"fernwick-fixture-key"}
TEXT = "Matter ID: M-3108. Order entered. Filed 2026-10-29."
INVALID = dict(matter_id=None, filing_type=None, filed_date=None, needs_review=True)
VALID = dict(matter_id="M-3108", filing_type="order", filed_date="2026-10-29")


def body(notice_id="N-1", tenant=ALDER, text=TEXT):
    return json.dumps(dict(notice_id=notice_id, inbox=INBOXES[tenant], text=text)).encode()


def signature(raw, tenant=ALDER):
    return hmac.new(SECRETS[tenant], raw, hashlib.sha256).hexdigest()


def deliver(client, notice_id="N-1", tenant=ALDER, text=TEXT):
    raw = body(notice_id, tenant, text)
    return client.post("/webhooks/notices", content=raw, headers={
        "content-type": "application/json", "X-Signature": signature(raw, tenant),
    })


def insert_notice(path, notice_id="N-1", tenant=ALDER, text=TEXT, status="received",
                  matter_id=None, filing_type=None, filed_date=None, needs_review=0):
    conn = connect(str(path))
    try:
        return conn.execute(
            "INSERT INTO notices(tenant_id, notice_id, text, status, matter_id, "
            "filing_type, filed_date, needs_review) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tenant, notice_id, text, status, matter_id, filing_type, filed_date, needs_review),
        ).lastrowid
    finally:
        conn.close()


def rows(path, table="notices"):
    assert table in {"notices", "calendar_entries"}
    conn = connect(str(path))
    try:
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
    finally:
        conn.close()
