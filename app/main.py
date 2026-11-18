"""FastAPI app: intake, approve and list routes (contract section 7)."""
import hashlib
import hmac
import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.db import connect, init_db


def _err(code: int, msg: str) -> JSONResponse:
    return JSONResponse(status_code=code, content={"detail": msg})


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI()
    setup = connect(db_path)
    init_db(setup)
    setup.close()

    def db():
        return connect(db_path)

    @app.post("/webhooks/notices")
    async def intake(request: Request):
        raw = await request.body()
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return _err(400, "invalid json")
        if not isinstance(payload, dict):
            return _err(400, "body must be an object")
        for field in ("notice_id", "inbox", "text"):
            if not isinstance(payload.get(field), str):
                return _err(400, f"{field} missing or not a string")

        conn = db()
        try:
            tenant = conn.execute(
                "SELECT tenant_id, secret FROM tenants WHERE inbox = ?",
                (payload["inbox"],),
            ).fetchone()
            if tenant is None:
                return _err(404, "unknown inbox")

            sig = request.headers.get("X-Signature")
            expected = hmac.new(
                tenant["secret"].encode(), json.dumps(payload).encode(), hashlib.sha256
            ).hexdigest()
            # Non-ASCII str would make compare_digest raise TypeError (500).
            if (
                sig is None
                or not sig.isascii()
                or not hmac.compare_digest(sig.lower(), expected)
            ):
                return _err(403, "bad signature")

            conn.execute(
                "INSERT INTO notices(tenant_id, notice_id, text, status) "
                "VALUES (?, ?, ?, 'received') "
                "ON CONFLICT(tenant_id, notice_id) DO NOTHING",
                (tenant["tenant_id"], payload["notice_id"], payload["text"]),
            )
            return {"ok": True}
        finally:
            conn.close()

    @app.post("/tenants/{tenant}/notices/{notice_id}/approve")
    def approve(tenant: str, notice_id: str):
        conn = db()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if conn.execute(
                    "SELECT 1 FROM tenants WHERE tenant_id = ?", (tenant,)
                ).fetchone() is None:
                    conn.execute("ROLLBACK")
                    return _err(404, "unknown tenant")
                row = conn.execute(
                    "SELECT id, status, matter_id, filed_date FROM notices "
                    "WHERE tenant_id = ? AND notice_id = ?",
                    (tenant, notice_id),
                ).fetchone()
                if row is None:
                    conn.execute("ROLLBACK")
                    return _err(404, "notice not found")
                if row["status"] == "docketed":
                    conn.execute("ROLLBACK")
                    return {"notice_id": notice_id, "status": "docketed"}
                if row["status"] in ("received", "processing") or row["matter_id"] is None:
                    conn.execute("ROLLBACK")
                    return _err(409, "notice not ready for approval")
                conn.execute(
                    "INSERT INTO calendar_entries(notice_pk, tenant_id, matter_id, filed_date) "
                    "VALUES (?, ?, ?, ?) ON CONFLICT(notice_pk) DO NOTHING",
                    (row["id"], tenant, row["matter_id"], row["filed_date"]),
                )
                conn.execute(
                    "UPDATE notices SET status = 'docketed', needs_review = 0 "
                    "WHERE id = ? AND tenant_id = ?",
                    (row["id"], tenant),
                )
                conn.execute("COMMIT")
                return {"notice_id": notice_id, "status": "docketed"}
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

    @app.get("/tenants/{tenant}/notices")
    def list_notices(tenant: str):
        conn = db()
        try:
            if conn.execute(
                "SELECT 1 FROM tenants WHERE tenant_id = ?", (tenant,)
            ).fetchone() is None:
                return _err(404, "unknown tenant")
            rows = conn.execute(
                "SELECT notice_id, matter_id, filing_type, filed_date, needs_review, status "
                "FROM notices WHERE tenant_id = ? ORDER BY id",
                (tenant,),
            ).fetchall()
            return [
                {
                    "notice_id": r["notice_id"],
                    "matter_id": r["matter_id"],
                    "filing_type": r["filing_type"],
                    "filed_date": r["filed_date"],
                    "needs_review": bool(r["needs_review"]),
                    "status": r["status"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    return app
