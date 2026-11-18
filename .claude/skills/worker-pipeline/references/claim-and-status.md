# Claim and status

Lifecycle: `received` -> `processing` (claim) -> `pending` (always, even for invalid answers) -> `docketed` (approve, not the worker's job).

## Claim (contract section 6)
```sql
UPDATE notices SET status='processing'
WHERE id = (SELECT id FROM notices WHERE status='received' ORDER BY id LIMIT 1)
  AND status='received'
RETURNING id, tenant_id, text
```
- The outer `AND status='received'` is the guard. If another worker claimed the row between the subquery and the update, the update matches zero rows.
- SQLite serialises writers. With `busy_timeout 5000`, the second worker waits instead of failing.
- Zero rows returned: either nothing is left, or you lost a race. Try the claim again; stop only when a fresh claim finds nothing.

## Finish
```sql
UPDATE notices SET status='pending', matter_id=?, filing_type=?, filed_date=?, needs_review=?
WHERE id=? AND status='processing'
```
Commit after each notice so a second worker sees progress.

## What can go wrong
| Mistake | Result |
|---|---|
| SELECT received rows, then loop and UPDATE | both workers extract the same notice |
| Claim without the outer status guard | same as above, under load |
| Leaving status `received` on invalid answers | notice is reprocessed forever |
| One transaction around the whole loop | second worker blocks until the first finishes |
