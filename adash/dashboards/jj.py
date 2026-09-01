"""JJ (Jarvis) command deck — ADash reads the JJ kernel, does not copy it."""

from __future__ import annotations

import sys
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from adash.paths import ROOT, VALID_STATES


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
    if verb == "dispatch":
        if len(tokens) < 2:
            raise ValueError("dispatch needs a task id")
        worker = "codex"
        if len(tokens) >= 3 and tokens[2].lower() in {"codex", "kimi"}:
            worker = tokens[2].lower()
        return "dispatch", {"task_id": int(tokens[1]), "worker": worker}
    raise ValueError(f"unknown command: {line}")


def snapshot(spec: dict[str, Any]) -> dict[str, Any]:
    try:
        cockpit_state, _, _, _ = _load(kernel_root(spec))
        state = cockpit_state(db_from_spec(spec))
        state["ok"] = True
        state["error"] = ""
        state["open_tasks"] = [t for t in state.get("tasks", []) if t.get("status") == "open"]
        state["working_tasks"] = [t for t in state.get("tasks", []) if t.get("status") == "working"]
        state["next_task"] = next_open_task(state["open_tasks"])
        state["event_total"] = sum(int(v) for v in (state.get("event_counts") or {}).values())
        state["live_dispatches"] = list_live_dispatches(spec, state.get("runs") or [])
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
            "next_task": None,
            "live_dispatches": [],
            "event_total": 0,
        }


def next_open_task(open_tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """P7-style: exactly one next task — lowest open id."""
    numbered: list[dict[str, Any]] = []
    for task in open_tasks:
        try:
            int(task.get("id"))
        except (TypeError, ValueError):
            continue
        numbered.append(task)
    if not numbered:
        return None
    return min(numbered, key=lambda task: int(task["id"]))


def split_globs(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").replace(";", ",").split(",") if part.strip()]


def format_brief(
    *,
    worker: str,
    run_id: int,
    task_id: int,
    title: str,
    assignment: dict[str, Any],
) -> str:
    allowed = ", ".join(assignment.get("files_allowed") or []) or "(none)"
    forbidden = ", ".join(assignment.get("files_forbidden") or []) or "(none)"
    return (
        f"# {worker} lane {run_id} — JJ task {task_id}\n"
        f"Title: {title}\n"
        f"Mission: {assignment.get('mission') or title}\n"
        f"Success test: {assignment.get('success_test') or ''}\n"
        f"Files allowed: {allowed}\n"
        f"Files forbidden: {forbidden}\n"
        f"Expected artifact: {assignment.get('expected_artifact') or '(none)'}\n"
        "\n"
        "Stay inside files_allowed. Do not expand scope.\n"
        "This lane is booked in the JJ kernel; the worker is NOT spawned.\n"
        "Paste this brief into Codex (or Kimi) yourself.\n"
    )


def write_brief_file(run_id: int, brief: str) -> Path:
    path = ROOT / "data" / "briefs" / f"run-{run_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(brief, encoding="utf-8")
    return path


def dispatch(
    spec: dict[str, Any],
    task_id: int,
    *,
    worker: str = "codex",
    mission: str = "",
    success_test: str = "",
    files_allowed: str = "",
    files_forbidden: str = "",
) -> dict[str, Any]:
    """C9: create a scoped subagent lane + paste-ready brief. Does not spawn a worker."""
    worker = (worker or "codex").strip().lower()
    if worker not in {"codex", "kimi"}:
        raise ValueError("dispatch worker must be codex or kimi")
    _, _, Ledger, TaskStore = _load(kernel_root(spec))
    from jj.adapters import SubagentAdapter

    db = db_from_spec(spec)
    with closing(Ledger(db)) as ledger:
        tasks = TaskStore(ledger)
        task = tasks.get_task(int(task_id))
        adapter = SubagentAdapter(ledger, worker=worker)
        allowed = split_globs(files_allowed) or ["jj/**", "tests/**"]
        forbidden = split_globs(files_forbidden)
        run_id = adapter.start(
            int(task_id),
            mission=(mission or "").strip() or str(task["title"]),
            success_test=(success_test or "").strip() or "python -m pytest -q",
            files_allowed=allowed,
            files_forbidden=forbidden or None,
        )
        assignment = adapter.get_assignment(run_id)
        brief = format_brief(
            worker=worker,
            run_id=run_id,
            task_id=int(task_id),
            title=str(task["title"]),
            assignment=assignment,
        )
        path = write_brief_file(run_id, brief)
        return {
            "ok": True,
            "result": f"{worker} lane {run_id} started (no spawn)",
            "run_id": run_id,
            "brief": brief,
            "brief_path": str(path),
        }


def list_live_dispatches(spec: dict[str, Any], runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    live = [
        run
        for run in runs
        if run.get("worker") in {"codex", "kimi"} and run.get("status") == "running"
    ]
    if not live:
        return []
    _, _, Ledger, TaskStore = _load(kernel_root(spec))
    from jj.adapters import SubagentAdapter

    out: list[dict[str, Any]] = []
    with closing(Ledger(db_from_spec(spec))) as ledger:
        tasks = TaskStore(ledger)
        adapters: dict[str, Any] = {}
        for run in live:
            worker = str(run["worker"])
            if worker not in adapters:
                adapters[worker] = SubagentAdapter(ledger, worker=worker)
            try:
                assignment = adapters[worker].get_assignment(int(run["id"]))
                task = tasks.get_task(int(run["task_id"]))
            except (ValueError, KeyError, TypeError):
                continue
            brief = format_brief(
                worker=worker,
                run_id=int(run["id"]),
                task_id=int(run["task_id"]),
                title=str(task["title"]),
                assignment=assignment,
            )
            out.append(
                {
                    "run_id": int(run["id"]),
                    "task_id": int(run["task_id"]),
                    "worker": worker,
                    "mission": assignment.get("mission") or "",
                    "brief": brief,
                    "title": task["title"],
                }
            )
    return out


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
    if kind == "dispatch":
        return dispatch(spec, int(payload["task_id"]), worker=str(payload.get("worker") or "codex"))
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
