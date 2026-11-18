# Validation rules for `check` (contract section 5)

Invalid result: `{"matter_id": None, "filing_type": None, "filed_date": None, "needs_review": True}`

| Answer | Valid? | Result |
|---|---|---|
| not a dict (None, list, str) | no | invalid |
| a key missing | no | invalid |
| `filing_type` not a str, or not in complaint/motion/order/other | no | invalid |
| `matter_id` not None and not a str | no | invalid |
| `matter_id` a str not in this tenant's matters (including one that exists only in the other tenant) | no | invalid |
| `filed_date` not None and not a str | no | invalid |
| `filed_date` a str that is not a real `YYYY-MM-DD` date (2026-02-30, 2026-13-01, 26-1-1) | no | invalid |
| extractor raised | no | invalid |
| all valid, `matter_id` None | yes | fields as given, `needs_review=True` |
| all valid, `filed_date` None | yes | fields as given |
| all valid with a matter of this tenant | yes | fields as given, `needs_review=False` |

Real date check: `datetime.date.fromisoformat` after a `^\d{4}-\d{2}-\d{2}$` match. The regex stops formats like `20261029` that `fromisoformat` accepts.

Extra keys in the answer are ignored.
