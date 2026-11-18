"""Review API: approve and list (contract section 7, brief Part C)."""
import pytest

from conftest import ALDER, FERN

CAL = "SELECT notice_pk, tenant_id, matter_id, filed_date FROM calendar_entries ORDER BY id"


def approve(client, tenant, notice_id):
    return client.post(f"/tenants/{tenant}/notices/{notice_id}/approve")


def pending(add_notice, tenant=ALDER, notice_id="N-1", matter="M-3108", review=0,
            date="2026-10-29"):
    return add_notice(tenant, notice_id, status="pending", matter_id=matter,
                      filing_type="order", filed_date=date, needs_review=review)


# ----------------------------------------------------------------- approve


def test_approve_pending_dockets_and_writes_calendar(client, add_notice, rows):
    pk = pending(add_notice)
    r = approve(client, ALDER, "N-1")
    assert r.status_code == 200, r.text
    assert rows(CAL) == [{"notice_pk": pk, "tenant_id": ALDER, "matter_id": "M-3108",
                          "filed_date": "2026-10-29"}]
    assert rows("SELECT status, needs_review FROM notices") == [
        {"status": "docketed", "needs_review": 0}]


def test_approve_with_null_filed_date(client, add_notice, rows):
    pk = pending(add_notice, date=None)
    assert approve(client, ALDER, "N-1").status_code == 200
    assert rows(CAL) == [{"notice_pk": pk, "tenant_id": ALDER, "matter_id": "M-3108",
                          "filed_date": None}]


def test_approve_clears_needs_review_when_matter_present(client, add_notice, rows):
    pending(add_notice, review=1)
    assert approve(client, ALDER, "N-1").status_code == 200
    assert rows("SELECT status, needs_review FROM notices") == [
        {"status": "docketed", "needs_review": 0}]
    assert len(rows(CAL)) == 1


@pytest.mark.parametrize("status", ["received", "processing"])
def test_approve_not_yet_extracted_409(client, add_notice, rows, status):
    add_notice(ALDER, "N-1", status=status)
    r = approve(client, ALDER, "N-1")
    assert r.status_code == 409, r.text
    assert rows(CAL) == []
    assert rows("SELECT status FROM notices") == [{"status": status}]


@pytest.mark.parametrize("status", ["received", "processing"])
def test_approve_not_yet_extracted_409_even_with_matter(client, add_notice, rows, status):
    add_notice(ALDER, "N-1", status=status, matter_id="M-3108", filing_type="order")
    assert approve(client, ALDER, "N-1").status_code == 409
    assert rows(CAL) == []


def test_approve_pending_null_matter_409(client, add_notice, rows):
    add_notice(ALDER, "N-1", status="pending", needs_review=1)
    r = approve(client, ALDER, "N-1")
    assert r.status_code == 409, r.text
    assert rows(CAL) == []
    assert rows("SELECT status, needs_review FROM notices") == [
        {"status": "pending", "needs_review": 1}]


def test_approve_unknown_tenant_404(client, add_notice, rows):
    pending(add_notice)
    r = approve(client, "nobody-llp", "N-1")
    assert r.status_code == 404, r.text
    assert rows(CAL) == []


def test_approve_unknown_notice_404(client, add_notice, rows):
    pending(add_notice)
    r = approve(client, ALDER, "NOPE")
    assert r.status_code == 404, r.text
    assert rows(CAL) == []


def test_approve_notice_of_other_tenant_404(client, add_notice, rows):
    pending(add_notice, tenant=ALDER, notice_id="ALDER-ONLY")
    r = approve(client, FERN, "ALDER-ONLY")
    assert r.status_code == 404, r.text
    assert rows(CAL) == []
    assert rows("SELECT status FROM notices") == [{"status": "pending"}]


def test_approve_same_notice_id_resolves_per_tenant(client, add_notice, rows):
    a = pending(add_notice, tenant=ALDER, notice_id="SAME", matter="M-3108")
    f = pending(add_notice, tenant=FERN, notice_id="SAME", matter="M-3108")
    assert approve(client, FERN, "SAME").status_code == 200
    assert rows(CAL) == [{"notice_pk": f, "tenant_id": FERN, "matter_id": "M-3108",
                          "filed_date": "2026-10-29"}]
    assert rows("SELECT id, status FROM notices ORDER BY id") == [
        {"id": a, "status": "pending"}, {"id": f, "status": "docketed"}]


def test_approve_twice_sequential_one_entry_two_200(client, add_notice, rows):
    pending(add_notice)
    r1 = approve(client, ALDER, "N-1")
    r2 = approve(client, ALDER, "N-1")
    assert (r1.status_code, r2.status_code) == (200, 200), (r1.text, r2.text)
    assert len(rows(CAL)) == 1
    assert rows("SELECT status FROM notices") == [{"status": "docketed"}]


def test_approve_docketed_without_calendar_row_is_200_no_change(client, add_notice, rows):
    # Contract row 3: docketed -> 200, no change.
    add_notice(ALDER, "N-1", status="docketed", matter_id="M-3108", filing_type="order")
    assert approve(client, ALDER, "N-1").status_code == 200
    assert rows(CAL) == []


@pytest.mark.parametrize("n", [2, 8])
def test_approve_concurrent_one_entry_all_200(make_client, add_notice, rows, concurrently, n):
    pending(add_notice)
    clients = [make_client() for _ in range(n)]
    results = concurrently([lambda c=c: approve(c, ALDER, "N-1") for c in clients])
    assert [r.status_code for r in results] == [200] * n, [r.text for r in results]
    assert len(rows(CAL)) == 1
    assert rows("SELECT status FROM notices") == [{"status": "docketed"}]


# -------------------------------------------------------------------- list

FIELDS = {"notice_id", "matter_id", "filing_type", "filed_date", "needs_review", "status"}


def test_list_unknown_tenant_404(client):
    assert client.get("/tenants/nobody-llp/notices").status_code == 404


@pytest.mark.parametrize("tenant", [ALDER, FERN])
def test_list_known_tenant_empty_is_empty_array(client, tenant):
    r = client.get(f"/tenants/{tenant}/notices")
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_list_scoped_to_tenant_ordered_by_id(client, add_notice):
    add_notice(ALDER, "A-1", status="received")
    add_notice(FERN, "F-1", status="pending", matter_id="M-4410", filing_type="motion",
               filed_date="2026-11-01")
    add_notice(ALDER, "A-2", status="pending", matter_id="M-3109", filing_type="complaint",
               filed_date="2026-10-30", needs_review=0)
    add_notice(ALDER, "A-3", status="pending", needs_review=1)

    r = client.get(f"/tenants/{ALDER}/notices")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    for item in body:
        assert set(item) >= FIELDS
    assert [{k: i[k] for k in FIELDS} for i in body] == [
        {"notice_id": "A-1", "matter_id": None, "filing_type": None, "filed_date": None,
         "needs_review": False, "status": "received"},
        {"notice_id": "A-2", "matter_id": "M-3109", "filing_type": "complaint",
         "filed_date": "2026-10-30", "needs_review": False, "status": "pending"},
        {"notice_id": "A-3", "matter_id": None, "filing_type": None, "filed_date": None,
         "needs_review": True, "status": "pending"},
    ]

    r = client.get(f"/tenants/{FERN}/notices")
    assert r.status_code == 200
    assert [{k: i[k] for k in FIELDS} for i in r.json()] == [
        {"notice_id": "F-1", "matter_id": "M-4410", "filing_type": "motion",
         "filed_date": "2026-11-01", "needs_review": False, "status": "pending"},
    ]


def test_list_needs_review_is_json_bool(client, add_notice):
    add_notice(ALDER, "A-1", status="pending", needs_review=1)
    add_notice(ALDER, "A-2", status="pending", matter_id="M-3108", filing_type="order")
    flags = [i["needs_review"] for i in client.get(f"/tenants/{ALDER}/notices").json()]
    assert flags == [True, False]
    assert all(type(f) is bool for f in flags)


def test_list_shows_docketed_after_approve(client, add_notice):
    pending(add_notice)
    assert approve(client, ALDER, "N-1").status_code == 200
    body = client.get(f"/tenants/{ALDER}/notices").json()
    assert [(i["notice_id"], i["status"], i["needs_review"]) for i in body] == [
        ("N-1", "docketed", False)]
