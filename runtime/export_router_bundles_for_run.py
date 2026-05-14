#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import time
import urllib.request

from swe_evo_env import default_router_api_base, default_router_db_path


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_started_at(value: str | None) -> int | None:
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def pick_external_ids(cli_kind: str, instance_id: str) -> list[str]:
    # In practice, some reruns have been labeled as `benchmark:cc:*` even when
    # the actual cli_kind is innercc, so always check both forms. Keep the
    # expected one first to bias toward the intended source.
    if cli_kind == "claude":
        return [f"benchmark:cc:{instance_id}", f"benchmark:innercc:{instance_id}"]
    if cli_kind == "innercc":
        return [f"benchmark:innercc:{instance_id}", f"benchmark:cc:{instance_id}"]
    return [f"benchmark:innercc:{instance_id}", f"benchmark:cc:{instance_id}"]


def fetch_bundle(router_api_base: str, run_id: str, timeout_seconds: int) -> dict:
    payload = json.dumps({"session_ids": [], "run_ids": [run_id], "trace_ids": []}).encode("utf-8")
    request = urllib.request.Request(
        f"{router_api_base.rstrip('/')}/api/export",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.load(response)


def table_columns(con: sqlite3.Connection, table: str) -> list[str]:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def rows_as_dicts(cur: sqlite3.Cursor, query: str, params: tuple) -> list[dict]:
    cur.execute(query, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_bundle_from_db(con: sqlite3.Connection, session_id: str, run_id: str) -> dict:
    cur = con.cursor()
    sessions = rows_as_dicts(cur, "SELECT * FROM sessions WHERE id = ?", (session_id,))
    runs = rows_as_dicts(cur, "SELECT * FROM runs WHERE id = ?", (run_id,))
    traces = rows_as_dicts(cur, "SELECT * FROM traces WHERE run_id = ? ORDER BY timestamp ASC", (run_id,))
    return {
        "version": 1,
        "exported_at": int(time.time() * 1000),
        "scope": {
            "session_ids": [session_id],
            "run_ids": [run_id],
            "trace_ids": [],
        },
        "counts": {
            "sessions": len(sessions),
            "runs": len(runs),
            "traces": len(traces),
        },
        "sessions": sessions,
        "runs": runs,
        "traces": traces,
    }


def find_latest_session_and_run(
    con: sqlite3.Connection,
    cli_kind: str,
    instance_id: str,
    started_at_ms: int | None,
) -> tuple[str | None, str | None]:
    session_id = None
    run_id = None

    for external_id in pick_external_ids(cli_kind, instance_id):
        row = con.execute(
            "SELECT id, created_at, updated_at FROM sessions WHERE external_id = ? ORDER BY updated_at DESC LIMIT 5",
            (external_id,),
        ).fetchall()
        if not row:
            continue
        picked_session = None
        if started_at_ms is not None:
            for candidate_id, created_at, updated_at in row:
                if int(updated_at) >= started_at_ms - 60_000:
                    picked_session = candidate_id
                    break
        if picked_session is None:
            picked_session = row[0][0]
        session_id = picked_session
        break

    if session_id is None:
        return None, None

    run_rows = con.execute(
        "SELECT id, created_at, updated_at FROM runs WHERE session_id = ? ORDER BY updated_at DESC",
        (session_id,),
    ).fetchall()
    if not run_rows:
        return session_id, None

    if started_at_ms is not None:
        for candidate_id, created_at, updated_at in run_rows:
            if int(updated_at) >= started_at_ms - 60_000:
                run_id = candidate_id
                break
    if run_id is None:
        run_id = run_rows[0][0]
    return session_id, run_id


def export_for_run_root(
    run_root: Path,
    router_db_path: Path,
    router_api_base: str,
    *,
    request_timeout_seconds: int,
    force: bool,
) -> int:
    metadata = load_json(run_root / "metadata.json", {})
    cli_kind = str(metadata.get("cli_kind") or "")
    infer_summary_path = run_root / "infer" / "inference_summary.json"
    summary = load_json(infer_summary_path, [])
    if not isinstance(summary, list):
        raise RuntimeError(f"invalid inference summary: {infer_summary_path}")

    updated = False
    exported = 0

    con = sqlite3.connect(str(router_db_path))
    try:
        for row in summary:
            instance_id = row.get("instance_id")
            if not instance_id:
                continue
            run_dir = run_root / "infer" / "runs" / instance_id
            bundle_path = run_dir / "router_trace_bundle.json"
            export_error_path = run_dir / "router_trace_bundle_error.txt"
            if not force and bundle_path.exists() and not export_error_path.exists():
                continue
            started_at_ms = parse_started_at(row.get("started_at"))
            session_id, run_id = find_latest_session_and_run(con, cli_kind, instance_id, started_at_ms)
            if run_id is None:
                continue

            try:
                bundle = fetch_bundle(router_api_base, run_id, request_timeout_seconds)
            except Exception as exc:
                bundle = fetch_bundle_from_db(con, session_id, run_id)
                print(json.dumps({
                    "instance_id": instance_id,
                    "router_run_id": run_id,
                    "export_fallback": "db",
                    "api_export_error": str(exc),
                }, ensure_ascii=False))

            if not isinstance(bundle, dict) or not bundle.get("traces"):
                continue

            write_json(bundle_path, bundle)
            if export_error_path.exists():
                export_error_path.unlink()
            row["router_session_id"] = session_id
            row["router_run_id"] = run_id
            row["router_export_error"] = None
            exported += 1
            updated = True
            print(json.dumps({
                "instance_id": instance_id,
                "router_session_id": session_id,
                "router_run_id": run_id,
                "trace_count": len(bundle.get("traces", [])),
            }, ensure_ascii=False))
    finally:
        con.close()

    if updated:
        write_json(infer_summary_path, summary)
    return exported


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re-export router trace bundles for a finished/in-flight run root")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--router-db-path", default=str(default_router_db_path()))
    parser.add_argument("--router-api-base", default=default_router_api_base())
    parser.add_argument("--request-timeout-seconds", type=int, default=45)
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_root = Path(args.run_root).resolve()
    router_db_path = Path(args.router_db_path).resolve()
    exported = export_for_run_root(
        run_root,
        router_db_path,
        args.router_api_base,
        request_timeout_seconds=args.request_timeout_seconds,
        force=args.force,
    )
    print(json.dumps({"run_root": str(run_root), "exported": exported}, ensure_ascii=False))


if __name__ == "__main__":
    main()
