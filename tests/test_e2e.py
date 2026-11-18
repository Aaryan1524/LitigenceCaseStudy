"""End to end on integrated code: signed webhook -> run_once (real extractor) -> approve -> list."""
from conftest import ALDER, EXAMPLE_BODY, EXAMPLE_SIG, FERN


def test_end_to_end_signed_webhook_worker_approve_list(db, client, post_notice, rows):
    from worker.run import run_once

    # 1. Signed webhook (contract section 8 example).
    r = post_notice(EXAMPLE_BODY, EXAMPLE_SIG)
    assert r.status_code == 200, r.text
    listed = client.get(f"/tenants/{ALDER}/notices").json()
    assert [(i["notice_id"], i["status"]) for i in listed] == [("NTC-8841", "received")]

    # Not yet extracted: approve must refuse.
    assert client.post(f"/tenants/{ALDER}/notices/NTC-8841/approve").status_code == 409

    # 2. Worker with the real default extractor.
    assert run_once(db) == 1
    listed = client.get(f"/tenants/{ALDER}/notices").json()
    assert len(listed) == 1
    item = listed[0]
    assert item["notice_id"] == "NTC-8841"
    assert item["status"] == "pending"
    assert item["matter_id"] == "M-3108"
    assert item["filing_type"] == "order"
    assert item["filed_date"] == "2026-10-29"
    assert item["needs_review"] is False

    # 3. Approve (twice: idempotent).
    assert client.post(f"/tenants/{ALDER}/notices/NTC-8841/approve").status_code == 200
    assert client.post(f"/tenants/{ALDER}/notices/NTC-8841/approve").status_code == 200

    # 4. List shows docketed; one calendar entry on alderbrook's M-3108.
    listed = client.get(f"/tenants/{ALDER}/notices").json()
    assert [(i["notice_id"], i["status"], i["matter_id"], i["needs_review"]) for i in listed] == [
        ("NTC-8841", "docketed", "M-3108", False)]
    assert rows("SELECT tenant_id, matter_id, filed_date FROM calendar_entries") == [
        {"tenant_id": ALDER, "matter_id": "M-3108", "filed_date": "2026-10-29"}]

    # Other tenant sees nothing.
    r = client.get(f"/tenants/{FERN}/notices")
    assert r.status_code == 200 and r.json() == []
