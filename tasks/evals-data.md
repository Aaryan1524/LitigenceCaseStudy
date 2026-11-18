# Task: evals-data (labelled notices)
Role `evals-data`. Runs as one LLM call with no tools: it cannot read, list or run anything. The architect's script saves its output to `evals/notices.jsonl` and commits it stamped `Agent-Role: evals-data`.
Input: this pack only (contract sections 2, 5, 9, 10).
Output: exactly 20 lines, each one JSON object in the section 10 format, and nothing else (no prose, no code fences).
Write each notice's text to follow section 9's conventions. Each label is the correct value after checking, worked out by hand from sections 5 and 9.
Must include:
- a matter ID valid only in the other tenant (all three expected fields null)
- an impossible calendar date (all three null)
- a notice whose text tells the reader to ignore its instructions (put the real `Matter ID:` line first; the injected text must not use the `Matter ID:` label; label the real matter)
- a valid notice with no date, and one with no matter
- M-3108 for both tenants
- all four filing types
Acceptance: the script validates 20 lines, the keys, and the tenants, and rejects the output otherwise.
