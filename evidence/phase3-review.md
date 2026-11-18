# Phase 3 review

Fresh `reviewer` agent (Opus), own read-only clone of main, session in `evidence/sessions.log`. Its report, verbatim:

---

Tests and evals pass. I've read all the code against the checklist and am writing up the findings now.

# Reviewer report

## What ran
- **`python -m pytest -q`**: all 143 tests passed (72 + 71 dots), with 1 harmless Starlette/httpx deprecation warning.
- **`python -m evals`**: all three fields (`filing_type`, `matter_id`, `filed_date`) scored 20/20 = 1.00.
- **Blocked:** my first attempt chained listing, pytest and evals into one shell command. It was auto-denied because the sandbox couldn't check a shell variable in it. Running each command on its own worked. I did not run any ad-hoc Python, since my brief limits Bash to pytest and evals. The scenarios below come from reading the code and Python/SQLite behaviour; I did not execute them.

## Checklist (all pass)
| Item | Where | Result |
|---|---|---|
| Signature over raw bytes | `app/main.py:27,48-51` | Body read once as bytes, HMAC over those bytes, `compare_digest`, all before the write |
| Uniqueness enforced by the database | `app/db.py:28,32`; `app/main.py:54-59, 89-93` | UNIQUE constraints plus `ON CONFLICT DO NOTHING` |
| Atomic claim | `worker/run.py:6-11,22` | Single `UPDATE … RETURNING` exactly as in contract §6; finish is guarded by `status='processing'` |
| Tenant scoping | `app/main.py:77,96,118`; `app/db.py:80` | Every notice lookup, list and matter lookup is keyed by tenant |
| Shared `run_extraction` | `evals/__main__.py:49`; `worker/run.py:37` | Evals and worker call the same function |
| Extractor gets text only | `worker/checks.py:61`; `extractor/extract.py:13` | One parameter; called with `text` only |
| Injection notice | `extractor/extract.py:8-10` | Only the fixed regexes count; text can't change behaviour |
| Approve order and idempotency | `app/main.py:68-100` | `BEGIN IMMEDIATE`, then 404 → 404 → docketed 200 → 409, then insert + update in one transaction |

No contract violations in the core safety properties. The five findings are edge cases where the code returns the wrong status or loses data.

## Findings (most severe first)

**1. A validly signed notice with a lone surrogate gets a 500 every time — `app/main.py:54-59`**
- **Scenario:** the vendor sends `{"notice_id":"N-1","inbox":"dockets@alderbrook-law.example","text":"bad \ud800 char"}` with a correct signature.
  - `json.loads` accepts it, so it passes the 400 checks, and the signature passes.
  - The `INSERT` then raises `UnicodeEncodeError` ("surrogates not allowed"), which nothing catches, so the response is 500.
  - The vendor retries forever and the notice is never stored. The same happens with a surrogate in `notice_id`.
- **Fix:** in the 400 validation step, reject strings that won't encode as UTF-8, e.g. `s.encode("utf-8")` in a try/except mapped to 400. Add an intake test for it.

**2. A non-ASCII `X-Signature` header gets a 500 instead of 403 — `app/main.py:51`**
- **Scenario:** a known inbox, plus a header sent as raw bytes `X-Signature: \xe9abc`.
  - Starlette decodes it as latin-1 to `"éabc"`.
  - `hmac.compare_digest` with a non-ASCII `str` raises `TypeError`, so the response is 500. Contract §7 row 3 requires 403.
- **Fix:** compare bytes, e.g. `hmac.compare_digest(sig.encode("latin-1"), expected.encode())`, or reject `not sig.isascii()` with 403. Add a test.

**3. `check` turns database errors into "invalid answer" and stores them permanently — `worker/checks.py:43,54-55`**
- **Scenario:** `matter_ids(conn, tenant_id)` raises `sqlite3.OperationalError` (e.g. `database is locked` after the busy timeout, or a disk I/O error) while the worker handles a notice whose extraction was correct (`M-3108`).
  - The blanket `except Exception` returns `_invalid()`.
  - The worker writes all three fields as null, `needs_review=1`, status `pending`. The correct extraction is lost, nothing is logged, and it's never retried.
- **Fix:** keep the never-raise rule for answer validation, but run `matter_ids(...)` outside the `try`, or re-raise `sqlite3.Error`. The worker then leaves the row in `processing` and logs it, which is the contract's crash case, instead of writing false data. This needs an architect decision because §4 says `check` "never raises".

**4. Deeply nested JSON gets a 500 instead of 400 — `app/main.py:28-31`**
- **Scenario:** POST a body of 100,000 `[` characters followed by 100,000 `]`.
  - `json.loads` raises `RecursionError`. That is not a `ValueError`, so it isn't caught, and the response is 500. Contract §7 row 1 requires 400.
- **Fix:** add `RecursionError` to the except tuple on line 30, and add it as a case in `test_malformed_body_400_and_no_row`.

**5. The intake handler is `async` but makes blocking SQLite calls — `app/main.py:26,38-59`**
- **Scenario:** a worker or an approve (`BEGIN IMMEDIATE`, line 68) holds the write lock while two vendor deliveries arrive.
  - The intake `INSERT` blocks inside the event loop for up to `busy_timeout` (5 s).
  - Every other request on that process stalls meanwhile, including GETs and approves, which run in the threadpool but can't be dispatched. Under load this becomes timeouts and retry storms.
  - Correctness holds, because uniqueness is still enforced by the database. Latency does not.
- **Fix:** read the body with `await request.body()`, then do the DB work in `await run_in_threadpool(...)`. Or split it into a sync helper called via `starlette.concurrency.run_in_threadpool`.

**Suggested picks for the two findings to act on:** #1 (a real poison-message loop with the retrying vendor) and #2 (a cheap fix that restores the contract's 403).

---

## Architect decisions (at most two findings acted on)
| # | Finding | Decision | Reason | Done by |
|---|---|---|---|---|
| 3 | A DB error in the matter lookup was stored as an invalid answer, silently losing a correct extraction | **Fixed** | Silent data corruption triggered by SQLite lock contention, the most likely production failure. Required a contract amendment (sections 4 and 6) | contract amended by architect; worker agent fixed; tests agent added tests |
| 2 | A non-ASCII `X-Signature` gave 500 instead of 403 | **Fixed** | Direct contract violation on the security path; cheap | contract clarified (section 7); api agent fixed; tests agent added tests |
| 1 | A lone-surrogate payload gives a permanent 500 (poison message) | Deferred | Needs a malformed vendor payload; listed under production risks | |
| 4 | Deeply nested JSON gives 500 | Deferred | Same family as 1 | |
| 5 | Blocking SQLite inside an async handler | Deferred | Latency, not correctness; listed under production risks | |

After the fixes: 156/156 tests pass; evals 1.00 on every field.
