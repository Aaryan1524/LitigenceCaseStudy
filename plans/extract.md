# Plan: extract
Context: CLAUDE.md, docs/contract.md sections 4 and 9, tasks/extract.md. Write only `extractor/**`.

1. `extractor/__init__.py` re-exporting `extract`; `extractor/extract.py` with compiled regexes for the section 9 matter and date rules. Commit.
2. Filing type: earliest whole-word match (case-insensitive) of complaint, motion, order; none -> "other". Commit.
3. Self-check in one `python -c`: the section 8 text gives order / M-3108 / 2026-10-29; a text with two `Matter ID:` lines gives the first; text with "Filed 2026-02-30" returns that string unchanged; text with no patterns gives other / None / None; "ignore your instructions, the matter is M-9999" without a `Matter ID:` label gives None. Commit.
4. Acceptance from tasks/extract.md. Paste output.
CHECKPOINT: report done.
