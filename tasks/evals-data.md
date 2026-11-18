# Task: evals-data (labelled notices)
Role `evals-data`. Branch `feat/evals-data`.
Owns: `evals/notices.jsonl` only. Reads: contract sections 2, 5, 9, 10 and the brief.
Hard separation: your checkout has no `extractor/`, `worker/` or `app/`, and you must not look for them.
Build: 20 synthetic notices in the format of contract section 10. Write the text to follow section 9's conventions. Each label is the correct value after checking, worked out by hand from sections 5 and 9, never by running code.
Must include:
- a matter ID valid only in the other tenant (all three expected fields null)
- an impossible calendar date (all three null)
- a notice whose text tells the reader to ignore its instructions (label the notice's real `Matter ID:` line, not the injected value)
- a valid notice with no date, and one with no matter
- M-3108 for both tenants
- all four filing types
You cannot run code (no python); you write the file and count lines with `wc -l`.
Acceptance: `wc -l evals/notices.jsonl` shows 20; paste one line per required case naming its `id`. The architect validates the JSON and sends back any errors.
