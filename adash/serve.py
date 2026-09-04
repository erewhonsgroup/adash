from __future__ import annotations

import json
import socket
from urllib.parse import quote
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from adash import VERSION
from adash.attention import score_attention
from adash.dashboards import custom_ids, spec_for
from adash.dashboards.jj import dispatch as jj_dispatch
from adash.dashboards.jj import execute as jj_execute
from adash.dashboards.jj import render_page as jj_render
from adash.db import connect, counts, get_project, init_db, insert_event, list_events, list_projects, upsert_project
from adash.inbox import annotate_needs_you, collect_inbox, jj_pending_counts, safe_return
from adash.ingest import ingest
from adash.paths import VALID_STATES, load_fleet, local_pc_id, now_stamp

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    fleet = load_fleet()
    app.state.fleet = fleet
    conn = connect(write=True)
    init_db(conn)
    n = conn.execute("SELECT COUNT(*) AS n FROM projects").fetchone()["n"]
    if n == 0:
        ingest(conn, fleet)
    conn.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ADash", version=VERSION, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
    app.state.fleet = load_fleet()

    def open_db(*, write: bool = True):
        conn = connect(write=write)
        if write:
            init_db(conn)
        return conn

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        fleet = app.state.fleet
        payload: dict[str, Any] = {
            "status": "ok",
            "version": VERSION,
            "hostname": socket.gethostname(),
            "pc": local_pc_id(fleet),
        }
        try:
            conn = open_db(write=True)
            payload["projects"] = conn.execute("SELECT COUNT(*) AS n FROM projects").fetchone()["n"]
            payload["last_ingest"] = ""
            row = conn.execute("SELECT value FROM meta WHERE key = 'last_ingest'").fetchone()
            if row:
                payload["last_ingest"] = row["value"]
            conn.close()
        except Exception as exc:  # noqa: BLE001 — healthz must not 500
            payload["projects"] = 0
            payload["db"] = "empty"
            payload["detail"] = str(exc.__class__.__name__)
        return payload

    def board_context(request: Request, pc: str, state: str, attention: str, q: str) -> dict[str, Any]:
        with closing(open_db(write=True)) as conn:
            projects = list_projects(conn, pc=pc, state=state, attention=attention, q=q)
            tally = counts(conn)
            last_ingest = ""
            meta = conn.execute("SELECT value FROM meta WHERE key = 'last_ingest'").fetchone()
            if meta:
                last_ingest = meta["value"]
        pending = jj_pending_counts(app.state.fleet)
        annotated = annotate_needs_you(projects, app.state.fleet, pending)
        return {
            "request": request,
            "projects": annotated,
            "pc": pc,
            "state": state,
            "attention": attention,
            "q": q,
            "tally": tally,
            "last_ingest": last_ingest,
            "pcs": [item["id"] for item in app.state.fleet.get("pcs", [])],
            "states": VALID_STATES,
            "local_pc": local_pc_id(app.state.fleet),
            "hostname": socket.gethostname(),
            "version": VERSION,
            "custom_dashboards": custom_ids(app.state.fleet),
            "needs_you_count": sum(1 for item in annotated if item.get("needs_you")),
        }

    @app.get("/", response_class=HTMLResponse)
    def board(
        request: Request,
        pc: str = "",
        state: str = "",
        attention: str = "",
        q: str = "",
    ) -> HTMLResponse:
        return templates.TemplateResponse(request, "board.html", board_context(request, pc, state, attention, q))

    @app.get("/fragment/board", response_class=HTMLResponse)
    def board_fragment(
        request: Request,
        pc: str = "",
        state: str = "",
        attention: str = "",
        q: str = "",
    ) -> HTMLResponse:
        return templates.TemplateResponse(request, "board_rows.html", board_context(request, pc, state, attention, q))

    @app.get("/inbox", response_class=HTMLResponse)
    def inbox_page(request: Request) -> HTMLResponse:
        with closing(open_db(write=True)) as conn:
            projects = list_projects(conn)
        items = collect_inbox(projects, app.state.fleet)
        return templates.TemplateResponse(
            request,
            "inbox.html",
            {
                "request": request,
                "items": items,
                "version": VERSION,
                "hostname": socket.gethostname(),
                "flash": str(request.query_params.get("flash") or ""),
                "flash_error": str(request.query_params.get("err") or ""),
            },
        )

    @app.get("/api/inbox")
    def api_inbox() -> JSONResponse:
        with closing(open_db(write=True)) as conn:
            projects = list_projects(conn)
        return JSONResponse(collect_inbox(projects, app.state.fleet))

    @app.get("/project/{project_id}", response_class=HTMLResponse)
    def project_local(project_id: str) -> RedirectResponse:
        pc = local_pc_id(app.state.fleet)
        return RedirectResponse(url=f"/project/{pc}/{project_id}", status_code=307)

    @app.get("/project/{pc}/{project_id}", response_class=HTMLResponse)
    def project_page(pc: str, project_id: str, request: Request) -> HTMLResponse:
        with closing(open_db(write=True)) as conn:
            row = get_project(conn, project_id, pc)
            events = list_events(conn, project_id, pc) if row else []
        if row is None:
            return templates.TemplateResponse(
                request,
                "missing.html",
                {
                    "project_id": project_id,
                    "pc": pc,
                    "version": VERSION,
                    "hostname": socket.gethostname(),
                },
                status_code=404,
            )
        groups = json.loads(row["groups_json"] or "[]")
        spec = spec_for(app.state.fleet, project_id)
        if spec and spec.get("kind") == "jj":
            return jj_render(
                request,
                templates,
                project=row,
                events=events,
                spec=spec,
                states=VALID_STATES,
                groups=groups,
                version=VERSION,
                hostname=socket.gethostname(),
                flash=str(request.query_params.get("flash") or ""),
                flash_error=str(request.query_params.get("err") or ""),
            )
        return templates.TemplateResponse(
            request,
            "project.html",
            {
                "project": row,
                "events": events,
                "states": VALID_STATES,
                "groups": groups,
                "version": VERSION,
                "hostname": socket.gethostname(),
            },
        )

    @app.post("/project/{pc}/{project_id}/command")
    def project_command(
        pc: str,
        project_id: str,
        line: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        spec = spec_for(app.state.fleet, project_id)
        target = safe_return(return_to, f"/project/{pc}/{project_id}")
        if not spec or spec.get("kind") != "jj":
            return RedirectResponse(url=target, status_code=303)
        try:
            result = jj_execute(spec, line)
            flash = quote(str(result.get("result") or "ok"), safe="")
            sep = "&" if "?" in target else "?"
            return RedirectResponse(url=f"{target}{sep}flash={flash}", status_code=303)
        except Exception as exc:  # noqa: BLE001 — command bar must bounce errors to the deck
            sep = "&" if "?" in target else "?"
            return RedirectResponse(url=f"{target}{sep}err={quote(str(exc), safe='')}", status_code=303)

    @app.post("/project/{pc}/{project_id}/dispatch")
    def project_dispatch(
        pc: str,
        project_id: str,
        task_id: int = Form(...),
        worker: str = Form("codex"),
        mission: str = Form(""),
        success_test: str = Form(""),
        files_allowed: str = Form(""),
        files_forbidden: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        spec = spec_for(app.state.fleet, project_id)
        target = safe_return(return_to, f"/project/{pc}/{project_id}")
        if not spec or spec.get("kind") != "jj":
            return RedirectResponse(url=target, status_code=303)
        try:
            result = jj_dispatch(
                spec,
                task_id,
                worker=worker,
                mission=mission,
                success_test=success_test,
                files_allowed=files_allowed,
                files_forbidden=files_forbidden,
            )
            flash = quote(str(result.get("result") or "ok"), safe="")
            sep = "&" if "?" in target else "?"
            return RedirectResponse(url=f"{target}{sep}flash={flash}", status_code=303)
        except Exception as exc:  # noqa: BLE001 — dispatch must bounce errors to the deck
            sep = "&" if "?" in target else "?"
            return RedirectResponse(url=f"{target}{sep}err={quote(str(exc), safe='')}", status_code=303)

    @app.get("/api/project/{pc}/{project_id}/kernel")
    def project_kernel(pc: str, project_id: str) -> JSONResponse:
        del pc
        spec = spec_for(app.state.fleet, project_id)
        if not spec or spec.get("kind") != "jj":
            return JSONResponse({"ok": False, "error": "no kernel dashboard"}, status_code=404)
        from adash.dashboards.jj import snapshot as jj_snapshot

        return JSONResponse(jj_snapshot(spec))

    @app.post("/project/{pc}/{project_id}/state")
    def write_state(
        pc: str,
        project_id: str,
        state: str = Form(...),
        task: str = Form(""),
        note: str = Form(""),
        blocker: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        target = safe_return(return_to, f"/project/{pc}/{project_id}")
        if state not in VALID_STATES:
            return RedirectResponse(url=target, status_code=303)
        with closing(open_db(write=True)) as conn:
            row = get_project(conn, project_id, pc)
            if row is None:
                return RedirectResponse(url="/", status_code=303)
            previous = row["state"]
            data = dict(row)
            data["state"] = state
            data["task"] = task
            data["note"] = note
            data["blocker"] = blocker
            data["updated_at"] = now_stamp()
            score, label, reason = score_attention(
                state=state,
                dirty=str(data.get("git_dirty") or ""),
                task=task,
                note=note,
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
                    "project_id": project_id,
                    "pc": pc,
                    "event_type": "state_changed",
                    "state": state,
                    "previous_state": previous,
                    "task": task,
                    "note": note,
                    "source": "adash",
                    "payload_json": json.dumps({"blocker": blocker}),
                },
            )
            conn.commit()
        return RedirectResponse(url=target, status_code=303)

    @app.post("/api/ingest")
    def api_ingest() -> dict[str, Any]:
        with closing(open_db(write=True)) as conn:
            result = ingest(conn, app.state.fleet)
        return {"ok": True, **result}

    @app.get("/api/projects")
    def api_projects(pc: str = "", state: str = "", attention: str = "", q: str = "") -> JSONResponse:
        with closing(open_db(write=True)) as conn:
            rows = [dict(item) for item in list_projects(conn, pc=pc, state=state, attention=attention, q=q)]
        return JSONResponse(rows)

    return app


app = create_app()
