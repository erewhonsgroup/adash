from __future__ import annotations

import argparse
import json
import os
import sys

from adash import VERSION
from adash.attention import score_attention
from adash.db import connect, get_project, init_db, insert_event, list_projects, upsert_project
from adash.ingest import ingest
from adash.paths import VALID_STATES, db_path, load_fleet, local_pc_id, now_stamp


def cmd_ingest(_args: argparse.Namespace) -> int:
    conn = connect(write=True)
    result = ingest(conn)
    conn.close()
    print(f"ingested {result['count']} project rows at {result['ingested_at']}")
    print(f"db {db_path()}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    path = db_path()
    if not path.exists():
        print("database is empty; run: python -m adash ingest", file=sys.stderr)
        return 1
    conn = connect(write=False)
    rows = list_projects(conn, pc=args.pc, state=args.state, q=args.q)
    conn.close()
    limit = args.limit
    print(f"{'attn':<14} {'state':<8} {'pc':<4} {'id':<22} {'task'}")
    print("-" * 88)
    for row in rows[:limit]:
        task = (row["task"] or row["reason"] or "")[:48]
        print(f"{row['attention']:<14} {row['state']:<8} {row['pc']:<4} {row['id']:<22} {task}")
    print(f"{min(limit, len(rows))} / {len(rows)} rows")
    return 0


def cmd_checkin(args: argparse.Namespace) -> int:
    if args.state not in VALID_STATES:
        print(f"invalid state {args.state!r}; expected one of {', '.join(VALID_STATES)}", file=sys.stderr)
        return 2
    fleet = load_fleet()
    pc = args.pc or local_pc_id(fleet)
    conn = connect(write=True)
    init_db(conn)
    row = get_project(conn, args.id, pc)
    if row is None:
        data = {
            "id": args.id,
            "pc": pc,
            "title": args.id,
            "path": os.getcwd(),
            "command": "",
            "groups_json": json.dumps(["checkin", pc]),
            "family": "",
            "purpose": "",
            "source": "checkin",
            "exists_on_disk": 1,
            "is_git": 0,
            "git_branch": "",
            "git_dirty": "",
            "origin": "",
            "state": args.state,
            "task": args.task,
            "note": args.note,
            "blocker": "",
            "evidence": "",
            "verification": "",
            "updated_at": now_stamp(),
            "last_launch": "",
            "attention_score": 100,
            "attention": "idle",
            "reason": "",
            "ingested_at": now_stamp(),
        }
    else:
        data = dict(row)
        data["state"] = args.state
        data["task"] = args.task
        data["note"] = args.note
        data["updated_at"] = now_stamp()
    score, label, reason = score_attention(
        state=data["state"],
        dirty=str(data.get("git_dirty") or ""),
        task=data["task"],
        note=data["note"],
        updated=data["updated_at"],
    )
    data["attention_score"] = score
    data["attention"] = label
    data["reason"] = reason
    upsert_project(conn, data)
    insert_event(
        conn,
        {
            "time": data["updated_at"],
            "project_id": args.id,
            "pc": pc,
            "event_type": "state_changed",
            "state": args.state,
            "previous_state": "" if row is None else row["state"],
            "task": args.task,
            "note": args.note,
            "source": "adash-checkin",
            "payload_json": "{}",
        },
    )
    conn.commit()
    conn.close()
    print(f"{args.id}@{pc} -> {args.state} ({label})")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from adash.serve import app

    fleet = load_fleet()
    host = args.host or fleet.get("listen_host") or "127.0.0.1"
    port = args.port or int(fleet.get("listen_port") or 8788)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adash", description="ADash control-center hub")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="cmd", required=True)

    ingest_p = sub.add_parser("ingest", help="rebuild the SQLite hub from AM + scan roots")
    ingest_p.set_defaults(func=cmd_ingest)

    status_p = sub.add_parser("status", help="print attention-sorted project rows")
    status_p.add_argument("--pc", default="")
    status_p.add_argument("--state", default="")
    status_p.add_argument("-q", default="")
    status_p.add_argument("--limit", type=int, default=40)
    status_p.set_defaults(func=cmd_status)

    checkin_p = sub.add_parser("checkin", help="write project state into the hub")
    checkin_p.add_argument("--id", default="adash")
    checkin_p.add_argument("--pc", default="")
    checkin_p.add_argument("--state", required=True, choices=VALID_STATES)
    checkin_p.add_argument("--task", default="")
    checkin_p.add_argument("--note", default="")
    checkin_p.set_defaults(func=cmd_checkin)

    serve_p = sub.add_parser("serve", help="run the dashboard")
    serve_p.add_argument("--host", default="")
    serve_p.add_argument("--port", type=int, default=0)
    serve_p.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
