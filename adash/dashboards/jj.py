"""JJ (Jarvis) command deck — ADash reads the JJ kernel, does not copy it."""

from __future__ import annotations

import sys
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from adash.paths import VALID_STATES


def db_from_spec(spec: dict[str, Any]) -> Path:
    raw = spec.get("db")
    if raw:
        return Path(raw)
    return Path.home() / ".jj" / "ledger.db"


def kernel_root(spec: dict[str, Any]) -> Path:
    return Path(str(spec.get("root") or r"C:\ALLU\projects\Jarvis"))


def _load(root: Path):
    root = Path(root)
    if not (root / "jj" / "cockpit.py").is_file():
        raise FileNotFoundError(f"JJ kernel not at {root}")
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
    from jj.cockpit import cockpit_action, cockpit_state
    from jj.ledger import Ledger
    from jj.tasks import TaskStore

    return cockpit_state, cockpit_action, Ledger, TaskStore


def parse_command(line: str) -> tuple[str, dict[str, Any]]:
    raw = (line or "").strip()
    if raw.startswith(":"):
        raw = raw[1:].strip()
    if not raw:
        raise ValueError("empty command")
    tokens = raw.split()
    verb = tokens[0].lower()
    if verb == "task" and len(tokens) >= 2:
        sub = tokens[1].lower()
        if sub == "add":
            title = raw.split(None, 2)[2] if len(tokens) >= 3 else ""
            if not title.strip():
                raise ValueError("task add needs a title")
            return "task.add", {"title": title.strip()}
        if sub in {"done", "drop"}:
            if len(tokens) < 3:
                raise ValueError(f"task {sub} needs an id")
            return f"task.{sub}", {"id": int(tokens[2])}
    if verb in {"approve", "deny"}:
        if len(tokens) < 2:
            raise ValueError(f"{verb} needs an id")
        return f"approval.{verb}", {"id": int(tokens[1])}
    if verb == "memory" and len(tokens) >= 3:
        sub = tokens[1].lower()
        if sub in {"approve", "reject"}:
            return f"memory.{sub}", {"id": int(tokens[2])}
    if verb == "skill" and len(tokens) >= 3 and tokens[1].lower() == "promote":
        return "skill.promote", {"name": tokens[2]}
    raise ValueError(f"unknown command: {line}")


def snapshot(spec: dict[str, Any]) -> dict[str, Any]:
    try:
        cockpit_state, _, _, _ = _load(kernel_root(spec))
        state = cockpit_state(db_from_spec(spec))
        state["ok"] = True
        state["error"] = ""
        state["open_tasks"] = [t for t in state.get("tasks", []) if t.get("status") == "open"]
        state["working_tasks"] = [t for t in state.get("tasks", []) if t.get("status") == "working"]
        state["event_total"] = sum(int(v) for v in (state.get("event_counts") or {}).values())
        return state
    except Exception as exc:  # noqa: BLE001 — deck must still render
        return {
            "ok": False,
            "error": f"{exc.__class__.__name__}: {exc}",
            "events": [],
            "event_counts": {},
            "tasks": [],
            "runs": [],
            "inbox": [],
            "decided": [],
            "passports": [],
            "skills": [],
            "memory_proposed": [],
            "memory_active": [],
            "open_tasks": [],
            "working_tasks": [],
            "event_total": 0,
        }


def execute(spec: dict[str, Any], line: str) -> dict[str, Any]:
    kind, payload = parse_command(line)
    db = db_from_spec(spec)
    _, cockpit_action, Ledger, TaskStore = _load(kernel_root(spec))
    if kind.startswith("task."):
        with closing(Ledger(db)) as ledger:
            store = TaskStore(ledger)
            if kind == "task.add":
                task_id = store.add_task(str(payload["title"]))
                return {"ok": True, "result": f"task {task_id} created"}
            status = "done" if kind == "task.done" else "dropped"
            store.set_task_status(int(payload["id"]), status)
            return {"ok": True, "result": f"task {payload['id']} {status}"}
    mapped = {
        "approval.approve": "approval.approve",
        "approval.deny": "approval.deny",
        "memory.approve": "memory.approve",
        "memory.reject": "memory.reject",
        "skill.promote": "skill.promote",
    }
    action = mapped.get(kind)
    if not action:
        raise ValueError(f"unhandled command {kind}")
    return {"ok": True, **cockpit_action(db, action, payload)}


def page_context(
    *,
    request: Any,
    project: Any,
    events: list,
    spec: dict[str, Any],
    states: tuple[str, ...] = VALID_STATES,
    groups: list[str],
    version: str,
    hostname: str,
    flash: str = "",
    flash_error: str = "",
) -> dict[str, Any]:
    kernel = snapshot(spec)
    return {
        "request": request,
        "project": project,
        "events": events,
        "states": states,
        "groups": groups,
        "version": version,
        "hostname": hostname,
        "kernel": kernel,
        "spec": spec,
        "kernel_root": str(kernel_root(spec)),
        "kernel_db": str(db_from_spec(spec)),
        "flash": flash,
        "flash_error": flash_error,
    }


def render_page(request: Any, templates: Jinja2Templates, **kwargs: Any) -> HTMLResponse:
    return templates.TemplateResponse(request, "jj.html", page_context(request=request, **kwargs))
