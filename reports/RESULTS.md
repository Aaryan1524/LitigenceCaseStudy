# Independent evaluation results

Snapshot: `97e1ccd938caf91a5896999cf9273e52f81ae398`  
Run time (UTC): 2026-11-19T00:18:44.531271+00:00  
Python: 3.14.6  
Platform: macOS-27.2.1-arm64-arm-64bit-Mach-O

| Check | Result |
| --- | --- |
| Contract, integration, CLI and process-concurrency tests | 160 passed; 0 failed |
| Eval filing_type | 20/20 (100%) |
| Eval matter_id | 20/20 (100%) |
| Eval filed_date | 20/20 (100%) |
| Eval exact match | 20/20 (100%) |
| Selected deliberate defects | 7/7 detected by assertion failures |
| Application integrity | All 10 Python files match the archived source revision |
| Original repository | Working tree unchanged |

No implementation defects were exposed by these checks. One dependency
warning was emitted: this installed Starlette version deprecates its httpx
TestClient integration. Tests still passed; the allowed direct dependencies
were preserved. Exact dependency versions are in `environment.txt`.

The process tests race two independently initialized applications for duplicate
intake and approval, and force two workers to enter extraction before either
can finish. All 18 worker inputs must be extracted exactly once.

The mutation checks run only in disposable copies, after a passing baseline:

- signature verification bypassed;
- signature computed over reserialized JSON;
- matter lookup includes both tenants;
- worker reclaims a processing notice;
- approval transaction removed;
- database lookup errors treated as invalid extraction;
- impossible calendar dates accepted.

This evaluates the synthetic contract and fixed parsing rules. It is not a
measurement of real legal-document accuracy, sustained load, live HTTP/proxy
behavior, production security, or crash recovery. The seven mutations are
selected safety probes, not an exhaustive mutation analysis.

Rerun instructions and coverage map: [../README.md](../README.md).
Raw evidence: `tests.xml`, `evals.json`, `mutations.json`, `run.json`,
`source-manifest.json`, `environment.txt`.
