import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.support import ALDER, FERN, TEXT, body, deliver, insert_notice, rows, signature
from worker.run import run_once

SIGNED_BODY = b'{"notice_id":"NTC-8841","inbox":"dockets@alderbrook-law.example","text":"Notice of filing. Matter ID: M-3108. Order on scheduling entered. Filed 2026-10-29. This is an automated notice; do not reply."}'
SIGNED_DIGEST = "4c741de4b7c0ab97653176ed0e3c6476e4f5a4142fe23295626f4c747d9523f2"


@pytest.mark.parametrize("raw", [b"{", b"", b"null", b"[]", b"42", b'"text"', b"\xff"])
def test_malformed_json_is_400_before_signature_check(client, db_path, raw):
    assert client.post("/webhooks/notices", content=raw).status_code == 400
    assert rows(db_path) == []


@pytest.mark.parametrize("field", ["notice_id", "inbox", "text"])
@pytest.mark.parametrize("bad", [None, 4, False, [], {}, "MISSING"])
def test_required_fields_are_strings(client, db_path, field, bad):
    payload = json.loads(body())
    if bad == "MISSING":
        del payload[field]
    else:
        payload[field] = bad
    raw = json.dumps(payload).encode()
    response = client.post("/webhooks/notices", content=raw,
                           headers={"X-Signature": signature(raw)})
    assert response.status_code == 400
    assert rows(db_path) == []


def test_unknown_inbox_precedes_missing_signature(client, db_path):
    raw = json.dumps(dict(notice_id="N", inbox="unknown@example.test", text=TEXT)).encode()
    assert client.post("/webhooks/notices", content=raw).status_code == 404
    assert rows(db_path) == []


@pytest.mark.parametrize("sig", [None, "", "0" * 64, "g" * 64, "a" * 63, "a" * 65, b"\xff", "sha256=abc"])
def test_bad_signature_never_writes(client, db_path, sig):
    headers = {} if sig is None else {"X-Signature": sig}
    assert client.post("/webhooks/notices", content=body(), headers=headers).status_code == 403
    assert rows(db_path) == []


def test_other_tenant_key_cannot_authorize_delivery(client, db_path):
    raw = body()
    response = client.post("/webhooks/notices", content=raw,
                           headers={"X-Signature": signature(raw, FERN)})
    assert response.status_code == 403
    assert rows(db_path) == []


def test_raw_bytes_are_signed_including_whitespace_and_unicode(client, db_path):
    raw = ('{\n "text": "Order — filed for café", "inbox": '
           '"dockets@alderbrook-law.example", "notice_id": "UNICODE"\n}').encode()
    assert client.post("/webhooks/notices", content=raw,
                       headers={"X-Signature": signature(raw)}).status_code == 200
    reformatted = json.dumps(json.loads(raw)).encode()
    assert client.post("/webhooks/notices", content=reformatted,
                       headers={"X-Signature": signature(raw)}).status_code == 403
    assert len(rows(db_path)) == 1


def test_published_signature_example(client, db_path):
    assert signature(SIGNED_BODY) == SIGNED_DIGEST
    response = client.post("/webhooks/notices", content=SIGNED_BODY,
                           headers={"X-Signature": SIGNED_DIGEST})
    assert response.status_code == 200
    row = rows(db_path)[0]
    assert row["status"] == "received"
    assert row["matter_id"] is None
    assert row["filing_type"] is None


def test_retry_keeps_entire_original_even_after_processing(client, db_path):
    assert deliver(client).status_code == 200
    assert run_once(str(db_path)) == 1
    original = rows(db_path)
    assert deliver(client, text="Replacement complaint. Matter ID: M-3109.").status_code == 200
    assert rows(db_path) == original
    assert run_once(str(db_path)) == 0


def test_same_notice_id_is_independent_across_tenants(client, db_path):
    assert deliver(client).status_code == 200
    assert deliver(client, tenant=FERN).status_code == 200
    assert {r["tenant_id"] for r in rows(db_path)} == {ALDER, FERN}


def test_list_is_scoped_ordered_and_does_not_expose_internals(client, db_path):
    insert_notice(db_path, "SECOND", tenant=FERN)
    insert_notice(db_path, "Z-FIRST", needs_review=1)
    insert_notice(db_path, "A-SECOND")
    response = client.get(f"/tenants/{ALDER}/notices")
    assert response.status_code == 200
    data = response.json()
    assert [item["notice_id"] for item in data] == ["Z-FIRST", "A-SECOND"]
    assert all(set(item) == {"notice_id", "matter_id", "filing_type", "filed_date", "needs_review", "status"}
               for item in data)
    assert [item["needs_review"] for item in data] == [True, False]
    assert all(type(item["needs_review"]) is bool for item in data)


def test_empty_and_unknown_tenant_lists(client):
    assert client.get(f"/tenants/{ALDER}/notices").json() == []
    assert client.get("/tenants/missing/notices").status_code == 404


@pytest.mark.parametrize("status,matter", [
    ("received", None), ("received", "M-3108"),
    ("processing", None), ("processing", "M-3108"), ("pending", None),
])
def test_unready_notice_cannot_be_approved(client, db_path, status, matter):
    insert_notice(db_path, status=status, matter_id=matter)
    before = rows(db_path)
    assert client.post(f"/tenants/{ALDER}/notices/N-1/approve").status_code == 409
    assert rows(db_path, "calendar_entries") == []
    assert rows(db_path) == before


@pytest.mark.parametrize("tenant,notice_id", [("missing", "N-1"), (FERN, "N-1"), (ALDER, "missing")])
def test_approval_lookup_is_tenant_scoped(client, db_path, tenant, notice_id):
    insert_notice(db_path, status="pending", matter_id="M-3108", needs_review=1)
    assert client.post(f"/tenants/{tenant}/notices/{notice_id}/approve").status_code == 404
    assert rows(db_path, "calendar_entries") == []


@pytest.mark.parametrize("filed_date", ["2026-10-29", None])
def test_approval_is_idempotent_and_clears_review(client, db_path, filed_date):
    pk = insert_notice(db_path, status="pending", matter_id="M-3108",
                       filing_type="order", filed_date=filed_date, needs_review=1)
    endpoint = f"/tenants/{ALDER}/notices/N-1/approve"
    assert client.post(endpoint).status_code == 200
    calendar = rows(db_path, "calendar_entries")
    assert len(calendar) == 1
    assert calendar[0] == dict(id=calendar[0]["id"], notice_pk=pk, tenant_id=ALDER,
                               matter_id="M-3108", filed_date=filed_date)
    assert client.post(endpoint).status_code == 200
    assert rows(db_path, "calendar_entries") == calendar
    assert rows(db_path)[0]["status"] == "docketed"
    assert rows(db_path)[0]["needs_review"] == 0


def test_approval_rolls_back_calendar_if_status_update_fails(db_path, conn):
    insert_notice(db_path, status="pending", matter_id="M-3108")
    conn.execute("CREATE TRIGGER fail_docket BEFORE UPDATE ON notices "
                 "WHEN NEW.status='docketed' BEGIN SELECT RAISE(ABORT, 'test fault'); END")
    with TestClient(create_app(str(db_path)), raise_server_exceptions=False) as client:
        assert client.post(f"/tenants/{ALDER}/notices/N-1/approve").status_code == 500
    assert rows(db_path, "calendar_entries") == []
    assert rows(db_path)[0]["status"] == "pending"


def test_end_to_end_both_tenants_shared_matter(client, db_path):
    for tenant in (ALDER, FERN):
        assert deliver(client, "SHARED", tenant).status_code == 200
    assert run_once(str(db_path)) == 2
    for tenant in (ALDER, FERN):
        assert client.post(f"/tenants/{tenant}/notices/SHARED/approve").status_code == 200
        assert client.get(f"/tenants/{tenant}/notices").json() == [dict(
            notice_id="SHARED", matter_id="M-3108", filing_type="order",
            filed_date="2026-10-29", needs_review=False, status="docketed",
        )]
    calendar = rows(db_path, "calendar_entries")
    assert len(calendar) == 2
    assert {r["tenant_id"] for r in calendar} == {ALDER, FERN}
