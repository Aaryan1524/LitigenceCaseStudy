# Phase 3: a test fails when its protection is removed

Protection: intake verifies the HMAC over the **original raw request bytes** (contract section 7).

1. The api agent (not the architect) made commit `8560e5b` (`DEMO: ...`), which computes the HMAC over `json.dumps(payload).encode()` instead:
   ```diff
   -                tenant["secret"].encode(), raw, hashlib.sha256
   +                tenant["secret"].encode(), json.dumps(payload).encode(), hashlib.sha256
   ```
2. The architect cherry-picked only that commit onto a scratch branch from main and ran pytest:
   ```
   FAILED tests/test_e2e.py::test_end_to_end_signed_webhook_worker_approve_list
   FAILED tests/test_intake.py::test_signed_example_accepted_and_stored_received
   FAILED tests/test_intake.py::test_non_ascii_signature_then_valid_delivery_still_accepted
   FAILED tests/test_intake.py::test_duplicate_sequential_one_row_both_200 - Ass...
   FAILED tests/test_intake.py::test_duplicate_does_not_reset_status - assert 40...
   FAILED tests/test_intake.py::test_duplicate_concurrent_deliveries_one_row[2]
   FAILED tests/test_intake.py::test_duplicate_concurrent_deliveries_one_row[8]
   7 failed, 149 passed, 1 warning in 1.28s
   ```
   The brief's own signed example is rejected: its bytes have no spaces after `:` or `,`, and `json.dumps` adds them, so the HMAC differs.
3. The api agent's next commit `4238fc1` (`Revert DEMO: ...`) restores the raw-bytes check. Net diff `969fe4d..4238fc1` is empty, the scratch branch was deleted, and main runs 156 passed.
