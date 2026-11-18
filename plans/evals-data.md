# Plan: evals-data
Context: CLAUDE.md, docs/contract.md sections 2, 5, 9, 10, tasks/evals-data.md. Write only `evals/notices.jsonl`.

1. Write a table (in your reply, not a file) of 20 cases: id, tenant, what it tests, expected fields. Cover every "Must include" item in tasks/evals-data.md, both tenants roughly evenly, all four filing types.
2. For each case, derive the label by hand: apply section 9 to the text, then section 5 against that tenant's matters (section 2 seed). State the reasoning for the three trap cases.
3. Write `evals/notices.jsonl`, one object per line. Commit.
4. Re-read the file with Read and check every line by eye: valid JSON, the section 10 keys, a seeded tenant. `wc -l` shows 20. Fix and commit.
5. Acceptance from tasks/evals-data.md. Paste output.
CHECKPOINT: report done.
