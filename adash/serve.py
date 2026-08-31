from __future__ import annotations

import json
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from adash import VERSION
from adash.attention import score_attention
from adash.db import connect, counts, get_project, init_db, insert_event, list_events, list_projects, upsert_project
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
        conn = open_db(write=True)
        projects = list_projects(conn, pc=pc, state=state, attention=attention, q=q)
        tally = counts(conn)
        last_ingest = ""
        meta = conn.execute("SELECT value FROM meta WHERE key = 'last_ingest'").fetchone()
        if meta:
            last_ingest = meta["value"]
        conn.close()
        return {
            "request": request,
            "projects": projects,
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

    @app.get("/project/{project_id}", response_class=HTMLResponse)
    def project_local(project_id: str) -> RedirectResponse:
        pc = local_pc_id(app.state.fleet)
        return RedirectResponse(url=f"/project/{pc}/{project_id}", status_code=307)

    @app.get("/project/{pc}/{project_id}", response_class=HTMLResponse)
    def project_page(pc: str, project_id: str, request: Request) -> HTMLResponse:
        conn = open_db(write=True)
        row = get_project(conn, project_id, pc)
        events = list_events(conn, project_id, pc) if row else []
        conn.close()
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
        return templates.TemplateResponse(
            request,
            "project.html",
            {
                "project": row,
                "events": events,
                "states": VALID_STATES,
                "groups": json.loads(row["groups_json"] or "[]"),
                "version": VERSION,
                "hostname": socket.gethostname(),
            },
        )

    @app.post("/project/{pc}/{project_id}/state")
    def write_state(
        pc: str,
        project_id: str,
        state: str = Form(...),
        task: str = Form(""),
        note: str = Form(""),
        blocker: str = Form(""),
    ) -> RedirectResponse:
        if state not in VALID_STATES:
            return RedirectResponse(url=f"/project/{pc}/{project_id}", status_code=303)
        conn = open_db(write=True)
        row = get_project(conn, project_id, pc)
        if row is None:
            conn.close()
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
        conn.close()
        return RedirectResponse(url=f"/project/{pc}/{project_id}", status_code=303)

    @app.post("/api/ingest")
    def api_ingest() -> dict[str, Any]:
        conn = open_db(write=True)
        result = ingest(conn, app.state.fleet)
        conn.close()
        return {"ok": True, **result}

    @app.get("/api/projects")
    def api_projects(pc: str = "", state: str = "", attention: str = "", q: str = "") -> JSONResponse:
        conn = open_db(write=True)
        rows = [dict(item) for item in list_projects(conn, pc=pc, state=state, attention=attention, q=q)]
        conn.close()
        return JSONResponse(rows)

    return app


app = create_app()
