"""Independent processes, real SQLite connections, bounded start/claim barriers."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import ALDER, VALID, body, signature


def wait_for(path):
    deadline = time.monotonic() + 12
    while not path.exists():
        if time.monotonic() > deadline:
            raise TimeoutError(f"barrier not released: {path.name}")
        time.sleep(0.01)


def main():
    kind, db_path, scratch, name = sys.argv[1:]
    scratch = Path(scratch)
    if kind in {"intake", "approve"}:
        from fastapi.testclient import TestClient
        from app.main import create_app
        client = TestClient(create_app(db_path))
    (scratch / f"{name}.ready").touch()
    wait_for(scratch / "release")
    if kind == "worker":
        from worker.run import run_once
        calls = []
        def fake(text):
            calls.append(text)
            (scratch / f"{name}.extracting").touch()
            wait_for(scratch / "extraction-release")
            return dict(VALID)
        count = run_once(db_path, extractor=fake)
        result = dict(count=count, calls=calls)
    else:
        with client:
            if kind == "intake":
                raw = body(text=f"original from {name}")
                response = client.post("/webhooks/notices", content=raw,
                                       headers={"X-Signature": signature(raw)})
            else:
                response = client.post(f"/tenants/{ALDER}/notices/N-1/approve")
        result = dict(status=response.status_code)
    (scratch / f"{name}.json").write_text(json.dumps(result))


if __name__ == "__main__":
    main()
