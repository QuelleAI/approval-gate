"""Approval Gate: offline, approval-first example for Python + SQLite.

This is intentionally not an automation service. No networking, messages, web
server, secrets, or third-party dependencies are used.
"""

import argparse
from collections import Counter
import hashlib
import json
import sqlite3

ALLOWED_KINDS = frozenset(("count_records", "find_duplicates"))
MAX_ITEMS = 1000
MAX_ITEM_LENGTH = 100
MAX_KEY_LENGTH = 120


class GateError(ValueError):
    """Invalid command, payload, or job state."""


def connect(db_path):
    """Open a local SQLite file. Caller closes the connection."""
    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,
            idempotency_hash TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            decided_at TEXT,
            completed_at TEXT,
            result_json TEXT,
            error_text TEXT,
            CHECK (state IN ('pending', 'approved', 'rejected', 'completed', 'failed'))
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            event TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    return conn


def _validate(kind, items, key):
    if kind not in ALLOWED_KINDS:
        raise GateError("Job kind is not on the read-only allowlist")
    if not isinstance(key, str) or not (1 <= len(key) <= MAX_KEY_LENGTH):
        raise GateError("Idempotency key must contain 1-120 characters")
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise GateError("Items must be a list with at most 1,000 entries")
    if any(not isinstance(v, str) or len(v) > MAX_ITEM_LENGTH for v in items):
        raise GateError("Each item must be text of at most 100 characters")


def _event(conn, job_id, event):
    conn.execute("INSERT INTO audit_events(job_id, event) VALUES (?, ?)", (job_id, event))


def _begin(conn):
    conn.execute("BEGIN IMMEDIATE")


def queue_job(conn, kind, items, key):
    """Queue a valid job as pending; a repeated key cannot change the payload."""
    _validate(kind, items, key)
    canonical = json.dumps({"items": items}, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    _begin(conn)
    try:
        existing = conn.execute(
            "SELECT id, kind, payload_json, state FROM jobs WHERE idempotency_hash=?",
            (digest,),
        ).fetchone()
        if existing is not None:
            if existing["kind"] != kind or existing["payload_json"] != canonical:
                raise GateError("Idempotency key already belongs to a different job")
            out = {"id": existing["id"], "state": existing["state"], "duplicate": True}
        else:
            cur = conn.execute(
                "INSERT INTO jobs(kind,idempotency_hash,payload_json) VALUES (?,?,?)",
                (kind, digest, canonical),
            )
            _event(conn, cur.lastrowid, "queued; requires explicit approval")
            out = {"id": cur.lastrowid, "state": "pending", "duplicate": False}
        conn.commit()
        return out
    except Exception:
        conn.rollback()
        raise


def decide_job(conn, job_id, decision):
    """Only a pending job may be approved or rejected."""
    if decision not in ("approved", "rejected"):
        raise GateError("Decision must be approved or rejected")
    _begin(conn)
    try:
        cur = conn.execute(
            "UPDATE jobs SET state=?, decided_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND state='pending'",
            (decision, job_id),
        )
        if cur.rowcount != 1:
            raise GateError("Job is missing or was already decided")
        _event(conn, job_id, decision)
        conn.commit()
        return {"id": job_id, "state": decision}
    except Exception:
        conn.rollback()
        raise


def _execute(kind, items):
    if kind == "count_records":
        return {"count": len(items)}
    if kind == "find_duplicates":
        counts = Counter(item.strip().casefold() for item in items)
        groups = {k: v for k, v in sorted(counts.items()) if v > 1}
        return {"duplicate_groups": groups, "duplicate_extra_records": sum(v - 1 for v in groups.values())}
    raise GateError("Unallowlisted job type cannot execute")


def run_next_approved(conn):
    """Run exactly one explicitly approved, read-only job, or return idle.

    A SQLite immediate transaction prevents two local workers from claiming the
    same job. The transaction ends before this method returns.
    """
    _begin(conn)
    try:
        row = conn.execute(
            "SELECT id,kind,payload_json FROM jobs WHERE state='approved' ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None:
            conn.commit()
            return {"state": "idle"}
        try:
            items = json.loads(row["payload_json"])["items"]
            result = _execute(row["kind"], items)
            conn.execute(
                "UPDATE jobs SET state='completed',completed_at=CURRENT_TIMESTAMP,result_json=? "
                "WHERE id=?", (json.dumps(result, sort_keys=True), row["id"])
            )
            _event(conn, row["id"], "completed read-only operation")
            outcome = {"id": row["id"], "state": "completed", "result": result}
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            conn.execute(
                "UPDATE jobs SET state='failed',completed_at=CURRENT_TIMESTAMP,error_text=? WHERE id=?",
                (type(exc).__name__, row["id"]),
            )
            _event(conn, row["id"], "failed")
            outcome = {"id": row["id"], "state": "failed"}
        conn.commit()
        return outcome
    except Exception:
        conn.rollback()
        raise


def list_jobs(conn):
    return [dict(row) for row in conn.execute(
        "SELECT id,kind,state,created_at,decided_at,completed_at FROM jobs ORDER BY id DESC"
    )]


def list_audit(conn):
    return [dict(row) for row in conn.execute(
        "SELECT job_id,event,created_at FROM audit_events ORDER BY id"
    )]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline approval-first job demonstration")
    parser.add_argument("--db", default="approval_gate_demo.db", help="Local SQLite path")
    actions = parser.add_subparsers(dest="command", required=True)
    q = actions.add_parser("queue")
    q.add_argument("--kind", choices=sorted(ALLOWED_KINDS), required=True)
    q.add_argument("--items", required=True, help='JSON list, e.g. ["alpha","beta"]')
    q.add_argument("--key", required=True, help="Unique idempotency key")
    d = actions.add_parser("decide")
    d.add_argument("--id", type=int, required=True)
    d.add_argument("--decision", choices=("approved", "rejected"), required=True)
    actions.add_parser("run-one")
    actions.add_parser("list")
    actions.add_parser("audit")
    args = parser.parse_args(argv)
    conn = connect(args.db)
    try:
        if args.command == "queue":
            result = queue_job(conn, args.kind, json.loads(args.items), args.key)
        elif args.command == "decide":
            result = decide_job(conn, args.id, args.decision)
        elif args.command == "run-one":
            result = run_next_approved(conn)
        elif args.command == "list":
            result = list_jobs(conn)
        else:
            result = list_audit(conn)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except (GateError, ValueError, sqlite3.Error) as exc:
        parser_message = f"ERROR: {exc}"
        raise SystemExit(parser_message)
