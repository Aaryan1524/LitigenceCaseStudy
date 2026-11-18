# One notice through the worker

Before (stored by intake):
| id | tenant_id | notice_id | status | matter_id | filing_type | filed_date | needs_review |
|---|---|---|---|---|---|---|---|
| 1 | alderbrook-law | NTC-8841 | received | null | null | null | 0 |

1. Claim: row 1 becomes `processing`.
2. `extract("Notice of filing. Matter ID: M-3108. Order on scheduling entered. Filed 2026-10-29. ...")`
   returns `{"filing_type": "order", "matter_id": "M-3108", "filed_date": "2026-10-29"}`.
3. `check(answer, "alderbrook-law", conn)`: M-3108 is an alderbrook-law matter, date is real, type is known. Valid.
4. Finish:

| id | tenant_id | notice_id | status | matter_id | filing_type | filed_date | needs_review |
|---|---|---|---|---|---|---|---|
| 1 | alderbrook-law | NTC-8841 | pending | M-3108 | order | 2026-10-29 | 0 |

The same text under fernwick-llp would also be valid, because fernwick-llp has its own M-3108. With `Matter ID: M-3109` it would be invalid for fernwick-llp: three nulls and `needs_review=1`.
