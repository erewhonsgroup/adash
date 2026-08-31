from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from adash.attention import score_attention
from adash.db import get_project, init_db, insert_event, set_meta, upsert_pc, upsert_project
from adash.paths import ROOT, load_fleet, local_pc_id, now_stamp
from adash.registry import load_am_state_file, parse_am_sessions, probe_path, scan_project_root


def parse_stamp(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def newer(left: str, right: str) -> bool:
    left_dt = parse_stamp(left)
    right_dt = parse_stamp(right)
    if left_dt is None:
        return False
    if right_dt is None:
        return True
    return left_dt >= right_dt


def groups_json(groups: list[str]) -> str:
    return json.dumps(groups, ensure_ascii=False)


def apply_probe(row: dict[str, Any]) -> None:
    probe = probe_path(row.get("path", ""))
    row.update(probe)
    if not row.get("purpose") and row.get("exists_on_disk") and row.get("path"):
        from adash.registry import read_purpose

        row["purpose"] = read_purpose(Path(row["path"]))


def apply_attention(row: dict[str, Any]) -> None:
    score, label, reason = score_attention(
        state=str(row.get("state") or "idle"),
        dirty=str(row.get("git_dirty") or ""),
        task=str(row.get("task") or ""),
        note=str(row.get("note") or ""),
        updated=str(row.get("updated_at") or ""),
    )
    row["attention_score"] = score
    row["attention"] = label
    row["reason"] = reason


def overlay_state(row: dict[str, Any], state: dict[str, Any]) -> None:
    updated = str(state.get("Updated") or state.get("updated") or "")
    if row.get("updated_at") and updated and not newer(updated, str(row["updated_at"])):
        return
    row["state"] = str(state.get("State") or state.get("state") or row.get("state") or "idle")
    row["task"] = str(state.get("Task") or state.get("task") or row.get("task") or "")
    row["note"] = str(state.get("Note") or state.get("note") or row.get("note") or "")
    row["blocker"] = str(state.get("Blocker") or state.get("blocker") or row.get("blocker") or "")
    row["evidence"] = str(state.get("Evidence") or state.get("evidence") or row.get("evidence") or "")
    row["verification"] = str(
        state.get("Verification") or state.get("verification") or row.get("verification") or ""
    )
    row["updated_at"] = updated or str(row.get("updated_at") or "")
    row["last_launch"] = str(state.get("LastLaunch") or state.get("last_launch") or row.get("last_launch") or "")


def latest_am_events(central_db: Path, limit: int = 2000) -> list[dict[str, Any]]:
    if not central_db.is_file():
        return []
    uri = f"file:{central_db.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=15)
    except sqlite3.Error:
        return []
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT time, event_type, session_id, COALESCE(NULLIF(source_pc, ''), pc, '') AS pc,
                   state, previous_state, task, note, title, folder
            FROM events
            WHERE session_id IS NOT NULL AND session_id != ''
            ORDER BY time DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except sqlite3.Error:
        conn.close()
        return []
    conn.close()
    return [dict(row) for row in rows]


def overlay_from_events(index: dict[tuple[str, str], dict[str, Any]], events: list[dict[str, Any]]) -> None:
    seen: set[tuple[str, str]] = set()
    for event in events:
        key = (str(event.get("session_id") or ""), str(event.get("pc") or ""))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        row = index.get(key)
        if row is None:
            continue
        event_time = str(event.get("time") or "")
        if row.get("updated_at") and event_time and not newer(event_time, str(row["updated_at"])):
            continue
        if event.get("state"):
            row["state"] = str(event["state"])
        if event.get("task") is not None:
            row["task"] = str(event.get("task") or "")
        if event.get("note") is not None:
            row["note"] = str(event.get("note") or "")
        if event_time:
            row["updated_at"] = event_time


def ensure_hub_project(index: dict[tuple[str, str], dict[str, Any]], pc: str) -> None:
    key = ("adash", pc)
    if key in index:
        return
    index[key] = {
        "id": "adash",
        "pc": pc,
        "title": "ADash",
        "path": str(ROOT),
        "command": "python",
        "groups": ["infra", "hub", pc],
        "family": "control",
        "purpose": "Central hub and database for the fleet control-center dashboard.",
        "source": "hub",
        "state": "idle",
        "task": "",
        "note": "",
        "blocker": "",
        "evidence": "",
        "verification": "",
        "updated_at": "",
        "last_launch": "",
        "origin": "",
        "git_branch": "",
    }


def collect_projects(fleet: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = fleet if fleet is not None else load_fleet()
    local_pc = local_pc_id(cfg)
    am_root = Path(str(cfg.get("am_root") or "C:\\AM"))
    state_dir = Path(str(cfg.get("am_state_dir") or am_root / "state"))
    central_db = Path(str(cfg.get("am_central_db") or am_root / "brain" / "central-am.db"))
    ingested_at = now_stamp()
    index: dict[tuple[str, str], dict[str, Any]] = {}

    for session in parse_am_sessions(am_root):
        key = (session["id"], session["pc"])
        row = {
            "id": session["id"],
            "pc": session["pc"],
            "title": session["title"],
            "path": session["path"],
            "command": session["command"],
            "groups": session["groups"],
            "family": "",
            "purpose": "",
            "source": "am-session",
            "state": "idle",
            "task": "",
            "note": "",
            "blocker": "",
            "evidence": "",
            "verification": "",
            "updated_at": "",
            "last_launch": "",
            "origin": "",
            "git_branch": "",
        }
        index[key] = row

    for raw_root in cfg.get("scan_roots", []):
        for scanned in scan_project_root(Path(str(raw_root)), local_pc):
            key = (scanned["id"], scanned["pc"])
            if key in index:
                if not index[key].get("purpose") and scanned.get("purpose"):
                    index[key]["purpose"] = scanned["purpose"]
                continue
            scanned.update(
                {
                    "family": "",
                    "state": "idle",
                    "task": "",
                    "note": "",
                    "blocker": "",
                    "evidence": "",
                    "verification": "",
                    "updated_at": "",
                    "last_launch": "",
                    "origin": "",
                    "git_branch": "",
                }
            )
            index[key] = scanned

    ensure_hub_project(index, local_pc)

    overlay_from_events(index, latest_am_events(central_db))

    if state_dir.is_dir():
        for (session_id, pc), row in index.items():
            if pc != local_pc:
                continue
            state = load_am_state_file(state_dir, session_id)
            if state:
                overlay_state(row, state)

    rows: list[dict[str, Any]] = []
    for row in index.values():
        apply_probe(row)
        apply_attention(row)
        row["groups_json"] = groups_json(list(row.get("groups") or []))
        row["ingested_at"] = ingested_at
        row["exists_on_disk"] = int(row.get("exists_on_disk") or 0)
        row["is_git"] = int(row.get("is_git") or 0)
        rows.append(row)
    return rows


LIVE_FIELDS = ("state", "task", "note", "blocker", "evidence", "verification", "updated_at", "last_launch")


def preserve_newer_hub_state(conn: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
    existing = get_project(conn, str(row["id"]), str(row["pc"]))
    if existing is None:
        return row
    incoming_updated = str(row.get("updated_at") or "")
    existing_updated = str(existing["updated_at"] or "")
    if incoming_updated and newer(incoming_updated, existing_updated):
        return row
    if not existing_updated:
        return row
    for field in LIVE_FIELDS:
        row[field] = existing[field]
    apply_attention(row)
    return row


def ingest(conn: sqlite3.Connection, fleet: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = fleet if fleet is not None else load_fleet()
    init_db(conn)
    for pc in cfg.get("pcs", []):
        upsert_pc(conn, str(pc["id"]), str(pc.get("hostname") or ""), str(pc.get("role") or "satellite"))
    rows = collect_projects(cfg)
    stamp = now_stamp()
    for row in rows:
        upsert_project(conn, preserve_newer_hub_state(conn, row))
    insert_event(
        conn,
        {
            "time": stamp,
            "project_id": "adash",
            "pc": local_pc_id(cfg),
            "event_type": "ingest",
            "state": "working",
            "previous_state": "",
            "task": f"ingested {len(rows)} project rows",
            "note": "",
            "source": "adash",
            "payload_json": json.dumps({"count": len(rows)}),
        },
    )
    set_meta(conn, "last_ingest", stamp)
    set_meta(conn, "project_count", str(len(rows)))
    conn.commit()
    return {"count": len(rows), "ingested_at": stamp}
