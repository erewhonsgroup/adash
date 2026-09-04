from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from adash.paths import SCHEMA_PATH, db_path


def connect(path: Path | None = None, *, write: bool = True) -> sqlite3.Connection:
    target = path or db_path()
    if write:
        target.parent.mkdir(parents=True, exist_ok=True)
    elif not target.is_file():
        raise FileNotFoundError(f"hub database not found: {target}")
    conn = sqlite3.connect(str(target), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if write:
        conn.execute("PRAGMA journal_mode = WAL")
    else:
        conn.execute("PRAGMA query_only = ON")
    return conn


def init_db(conn: sqlite3.Connection, schema_path: Path | None = None) -> None:
    sql = (schema_path or SCHEMA_PATH).read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else default


def upsert_pc(conn: sqlite3.Connection, pc_id: str, hostname: str, role: str) -> None:
    conn.execute(
        """
        INSERT INTO pcs(id, hostname, role) VALUES(?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET hostname = excluded.hostname, role = excluded.role
        """,
        (pc_id, hostname, role),
    )


def upsert_project(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    cols = [
        "id",
        "pc",
        "title",
        "path",
        "command",
        "groups_json",
        "family",
        "purpose",
        "source",
        "exists_on_disk",
        "is_git",
        "git_branch",
        "git_dirty",
        "origin",
        "state",
        "task",
        "note",
        "blocker",
        "evidence",
        "verification",
        "updated_at",
        "last_launch",
        "attention_score",
        "attention",
        "reason",
        "ingested_at",
    ]
    values = [row.get(col, "" if col not in {"exists_on_disk", "is_git", "attention_score"} else 0) for col in cols]
    placeholders = ", ".join("?" for _ in cols)
    assignments = ", ".join(f"{col} = excluded.{col}" for col in cols if col not in {"id", "pc"})
    conn.execute(
        f"INSERT INTO projects ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT(id, pc) DO UPDATE SET {assignments}",
        values,
    )


def insert_event(conn: sqlite3.Connection, event: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO events (time, project_id, pc, event_type, state, previous_state, task, note, source, payload_json)
        VALUES (:time, :project_id, :pc, :event_type, :state, :previous_state, :task, :note, :source, :payload_json)
        """,
        {
            "time": event.get("time", ""),
            "project_id": event.get("project_id", ""),
            "pc": event.get("pc", ""),
            "event_type": event.get("event_type", ""),
            "state": event.get("state", ""),
            "previous_state": event.get("previous_state", ""),
            "task": event.get("task", ""),
            "note": event.get("note", ""),
            "source": event.get("source", ""),
            "payload_json": event.get("payload_json", "{}"),
        },
    )


def list_projects(
    conn: sqlite3.Connection,
    *,
    pc: str = "",
    state: str = "",
    attention: str = "",
    q: str = "",
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[Any] = []
    if pc:
        clauses.append("pc = ?")
        params.append(pc)
    if state:
        clauses.append("state = ?")
        params.append(state)
    if attention:
        clauses.append("attention = ?")
        params.append(attention)
    if q:
        like = f"%{q.lower()}%"
        clauses.append(
            "(lower(id) LIKE ? OR lower(title) LIKE ? OR lower(path) LIKE ? OR lower(task) LIKE ? OR lower(note) LIKE ?)"
        )
        params.extend([like, like, like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM projects {where} ORDER BY attention_score ASC, updated_at DESC, id ASC"
    return list(conn.execute(sql, params).fetchall())


def get_project(conn: sqlite3.Connection, project_id: str, pc: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM projects WHERE id = ? AND pc = ?",
        (project_id, pc),
    ).fetchone()


def list_events(conn: sqlite3.Connection, project_id: str, pc: str, limit: int = 50) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT * FROM events
            WHERE project_id = ? AND (pc = ? OR pc = '')
            ORDER BY time DESC, id DESC
            LIMIT ?
            """,
            (project_id, pc, limit),
        ).fetchall()
    )


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    total = conn.execute("SELECT COUNT(*) AS n FROM projects").fetchone()["n"]
    by_state = {
        row["state"]: row["n"]
        for row in conn.execute("SELECT state, COUNT(*) AS n FROM projects GROUP BY state")
    }
    by_pc = {
        row["pc"]: row["n"]
        for row in conn.execute("SELECT pc, COUNT(*) AS n FROM projects GROUP BY pc")
    }
    return {"projects": int(total), **{f"state:{k}": int(v) for k, v in by_state.items()}, **{f"pc:{k}": int(v) for k, v in by_pc.items()}}


def rows_as_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
