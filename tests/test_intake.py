"""Intake: POST /webhooks/notices (contract section 7, brief Part A)."""
import json

import pytest

from conftest import (
    ALDER, ALDER_INBOX, EXAMPLE_BODY, EXAMPLE_SIG, EXAMPLE_TEXT, FERN, FERN_INBOX,
    SECRETS, body_for, sign,
)

COUNT = "SELECT COUNT(*) AS n FROM notices"


def count(rows):
    return rows(COUNT)[0]["n"]


# ------------------------------------------------------------- happy path


def test_signed_example_accepted_and_stored_received(post_notice, rows):
    # Sanity: our helper reproduces the contract's signature over the exact bytes.
    assert sign(EXAMPLE_BODY, SECRETS[ALDER]) == EXAMPLE_SIG
    r = post_notice(EXAMPLE_BODY, EXAMPLE_SIG)
    assert r.status_code == 200, r.text
    stored = rows("SELECT * FROM notices")
    assert len(stored) == 1
    n = stored[0]
    assert n["tenant_id"] == ALDER
    assert n["notice_id"] == "NTC-8841"
    assert n["text"] == EXAMPLE_TEXT
    assert n["status"] == "received"
    # Intake never extracts.
    assert n["matter_id"] is None
    assert n["filing_type"] is None
    assert n["filed_date"] is None


def test_second_tenant_accepted_with_its_own_secret(post_notice, rows):
    body = body_for("F-1", FERN_INBOX, "Matter ID: M-4410. Motion. Filed 2026-11-01.")
    r = post_notice(body, sign(body, SECRETS[FERN]))
    assert r.status_code == 200, r.text
    assert rows("SELECT tenant_id, status FROM notices") == [
        {"tenant_id": FERN, "status": "received"}
    ]


# ------------------------------------------------------------ bad signature


def _flip_last_hex(sig):
    return sig[:-1] + ("0" if sig[-1] != "0" else "1")


@pytest.mark.parametrize(
    "signature",
    [
        _flip_last_hex(EXAMPLE_SIG),                       # one char wrong
        sign(EXAMPLE_BODY, SECRETS[FERN]),                 # other tenant's secret
        sign(EXAMPLE_BODY, "wrong-key"),                   # unknown key
        "",                                                # empty header
        "not-hex-at-all",
        EXAMPLE_SIG[:32],                                  # truncated
    ],
    ids=["one-char", "other-tenant-key", "wrong-key", "empty", "garbage", "truncated"],
)
def test_bad_signature_403_and_no_row(post_notice, rows, signature):
    r = post_notice(EXAMPLE_BODY, signature)
    assert r.status_code == 403, r.text
    assert count(rows) == 0


def test_missing_signature_403_and_no_row(post_notice, rows):
    r = post_notice(EXAMPLE_BODY, None)
    assert r.status_code == 403, r.text
    assert count(rows) == 0


def test_signature_checked_over_raw_bytes_not_reserialised_json(post_notice, rows):
    # Same JSON object, different bytes: the signature over the original bytes
    # must not validate the reformatted body.
    reformatted = json.dumps(json.loads(EXAMPLE_BODY), indent=2).encode()
    assert reformatted != EXAMPLE_BODY
    r = post_notice(reformatted, EXAMPLE_SIG)
    assert r.status_code == 403, r.text
    assert count(rows) == 0


def test_tampered_body_with_original_signature_403(post_notice, rows):
    tampered = EXAMPLE_BODY.replace(b"M-3108", b"M-3109")
    r = post_notice(tampered, EXAMPLE_SIG)
    assert r.status_code == 403, r.text
    assert count(rows) == 0


# ------------------------------------------------------------- 400 and 404


def _signed_alder(body):
    return sign(body, SECRETS[ALDER])


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"",
        b'{"notice_id": "X-1", "inbox": ',                              # truncated JSON
        b'["NTC-1", "dockets@alderbrook-law.example", "text"]',          # array
        b'"just a string"',
        b"42",
        b"null",
        json.dumps({"inbox": ALDER_INBOX, "text": "t"}).encode(),        # no notice_id
        json.dumps({"notice_id": "X-1", "text": "t"}).encode(),          # no inbox
        json.dumps({"notice_id": "X-1", "inbox": ALDER_INBOX}).encode(),  # no text
        json.dumps({"notice_id": 123, "inbox": ALDER_INBOX, "text": "t"}).encode(),
        json.dumps({"notice_id": "X-1", "inbox": ALDER_INBOX, "text": None}).encode(),
        json.dumps({"notice_id": "X-1", "inbox": [ALDER_INBOX], "text": "t"}).encode(),
        json.dumps({"notice_id": "X-1", "inbox": ALDER_INBOX, "text": {"a": 1}}).encode(),
    ],
    ids=[
        "garbage", "empty", "truncated", "array", "string", "number", "null",
        "no-notice_id", "no-inbox", "no-text", "int-notice_id", "null-text",
        "list-inbox", "object-text",
    ],
)
def test_malformed_body_400_and_no_row(post_notice, rows, body):
    # Signed with a valid key so the result does not depend on check order;
    # contract order puts 400 first anyway.
    r = post_notice(body, _signed_alder(body))
    assert r.status_code == 400, r.text
    assert count(rows) == 0


def test_malformed_body_without_signature_is_400(post_notice, rows):
    r = post_notice(b"not json", None)
    assert r.status_code == 400, r.text
    assert count(rows) == 0


def test_unknown_inbox_404_and_no_row(post_notice, rows):
    body = body_for("X-1", "dockets@nobody.example", "Matter ID: M-3108.")
    r = post_notice(body, _signed_alder(body))
    assert r.status_code == 404, r.text
    assert count(rows) == 0


def test_unknown_inbox_without_signature_is_404(post_notice, rows):
    body = body_for("X-1", "dockets@nobody.example", "t")
    r = post_notice(body, None)
    assert r.status_code == 404, r.text
    assert count(rows) == 0


# --------------------------------------------------------------- duplicates


def test_duplicate_sequential_one_row_both_200(post_notice, rows):
    r1 = post_notice(EXAMPLE_BODY, EXAMPLE_SIG)
    r2 = post_notice(EXAMPLE_BODY, EXAMPLE_SIG)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert count(rows) == 1


def test_duplicate_keeps_original_text(post_notice, rows):
    first = body_for("DUP-1", ALDER_INBOX, "original text")
    second = body_for("DUP-1", ALDER_INBOX, "replacement text")
    assert post_notice(first, _signed_alder(first)).status_code == 200
    r = post_notice(second, _signed_alder(second))
    assert r.status_code == 200, r.text
    assert rows("SELECT text FROM notices") == [{"text": "original text"}]


def test_duplicate_does_not_reset_status(db, post_notice, rows):
    import sqlite3

    assert post_notice(EXAMPLE_BODY, EXAMPLE_SIG).status_code == 200
    # Simulate the worker having moved it on.
    c = sqlite3.connect(db, timeout=10)
    c.execute("UPDATE notices SET status='pending', matter_id='M-3108', filing_type='order'")
    c.commit()
    c.close()
    assert post_notice(EXAMPLE_BODY, EXAMPLE_SIG).status_code == 200
    assert rows("SELECT status, matter_id FROM notices") == [
        {"status": "pending", "matter_id": "M-3108"}
    ]


def test_same_notice_id_in_two_tenants_is_two_rows(post_notice, rows):
    a = body_for("SHARED-1", ALDER_INBOX, "alder text")
    f = body_for("SHARED-1", FERN_INBOX, "fern text")
    assert post_notice(a, sign(a, SECRETS[ALDER])).status_code == 200
    assert post_notice(f, sign(f, SECRETS[FERN])).status_code == 200
    got = rows("SELECT tenant_id, notice_id, text FROM notices ORDER BY tenant_id")
    assert got == [
        {"tenant_id": ALDER, "notice_id": "SHARED-1", "text": "alder text"},
        {"tenant_id": FERN, "notice_id": "SHARED-1", "text": "fern text"},
    ]


@pytest.mark.parametrize("n", [2, 8])
def test_duplicate_concurrent_deliveries_one_row(make_client, post_notice, rows,
                                                 concurrently, n):
    clients = [make_client() for _ in range(n)]
    results = concurrently(
        [lambda c=c: post_notice(EXAMPLE_BODY, EXAMPLE_SIG, c=c) for c in clients]
    )
    assert [r.status_code for r in results] == [200] * n, [r.text for r in results]
    assert count(rows) == 1
    assert rows("SELECT notice_id, status FROM notices") == [
        {"notice_id": "NTC-8841", "status": "received"}
    ]
