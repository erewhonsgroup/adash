from __future__ import annotations

from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adash.dashboards.jj import next_open_task
from adash.inbox import collect_inbox, hub_needs_you
from adash.serve import create_app
from conftest import make_am_root, write_fleet

JJ_ROOT = Path(r"C:\ALLU\projects\Jarvis")
pytestmark = pytest.mark.skipif(
    not (JJ_ROOT / "jj" / "cockpit.py").is_file(),
    reason="JJ kernel is not at C:\\ALLU\\projects\\Jarvis",
)


def test_next_open_task_is_lowest_id():
    first = next_open_task(
        [
            {"id": 7, "title": "later"},
            {"id": 2, "title": "first open"},
            {"id": 4, "title": "mid"},
        ]
    )
    assert first is not None
    assert first["id"] == 2
    assert next_open_task([]) is None


def test_hub_needs_you():
    assert hub_needs_you("review") is True
    assert hub_needs_you("blocked") is True
    assert hub_needs_you("working") is False


def _seed_jj(db: Path) -> None:
    import sys

    if str(JJ_ROOT) not in sys.path:
        sys.path.insert(0, str(JJ_ROOT))
    from jj.approvals import ApprovalStore
    from jj.ledger import Ledger
    from jj.tasks import TaskStore

    with closing(Ledger(db)) as ledger:
        tasks = TaskStore(ledger)
        tasks.add_task("first-open")
        tasks.add_task("second-open")
        ApprovalStore(ledger).request("tool", "codex", "needs a grant")


def test_inbox_needs_you_and_next_task(tmp_path, monkeypatch):
    am_root = make_am_root(tmp_path)
    (am_root / "scripts" / "AM.Sessions.ps1").write_text(
        (am_root / "scripts" / "AM.Sessions.ps1").read_text(encoding="utf-8")
        + "\n  New-AMSession -Id 'jarvis' -Title 'JJ' -Folder 'C:\\ALLU\\projects\\Jarvis' -Group 'pc1'\n",
        encoding="utf-8",
    )
    jj_db = tmp_path / "ledger.db"
    _seed_jj(jj_db)
    fleet = write_fleet(
        tmp_path,
        am_root,
        extra={
            "project_dashboards": {
                "jarvis": {"kind": "jj", "root": str(JJ_ROOT), "db": str(jj_db)}
            }
        },
    )
    monkeypatch.setenv("ADASH_FLEET", str(fleet))
    monkeypatch.setenv("ADASH_DB", str(tmp_path / "adash.db"))
    with TestClient(create_app()) as client:
        am = client.post(
            "/project/pc1/am/state",
            data={"state": "review", "task": "review the fleet", "note": "spot check", "blocker": ""},
            follow_redirects=False,
        )
        assert am.status_code == 303
        academy = client.post(
            "/project/pc1/academy/state",
            data={"state": "blocked", "task": "needs a key", "note": "", "blocker": "missing token"},
            follow_redirects=False,
        )
        assert academy.status_code == 303

        inbox = client.get("/api/inbox").json()
        kinds = {item["kind"] for item in inbox}
        assert "hub" in kinds
        assert "jj-approval" in kinds
        hub_states = {item["state"] for item in inbox if item["kind"] == "hub"}
        assert "review" in hub_states
        assert "blocked" in hub_states
        page = client.get("/inbox")
        assert page.status_code == 200
        assert "Needs Joshua" in page.text
        assert "review the fleet" in page.text
        assert "needs a grant" in page.text or "codex" in page.text
        assert "Working" in page.text
        assert "Approve" in page.text

        board = client.get("/")
        assert board.status_code == 200
        assert "needs you" in board.text
        assert 'href="/project/pc1/jarvis"' in board.text
        assert "deck" in board.text

        kernel = client.get("/api/project/pc1/jarvis/kernel").json()
        assert kernel["ok"] is True
        assert kernel["next_task"] is not None
        assert kernel["next_task"]["id"] == min(t["id"] for t in kernel["open_tasks"])
        assert kernel["next_task"]["title"] == "first-open"
        deck = client.get("/project/pc1/jarvis")
        assert ">next</span>" in deck.text
        assert "first-open" in deck.text

        working = client.post(
            "/project/pc1/am/state",
            data={
                "state": "working",
                "task": "review the fleet",
                "note": "spot check",
                "blocker": "",
                "return_to": "/inbox",
            },
            follow_redirects=True,
        )
        assert working.status_code == 200
        after_hub = client.get("/api/inbox").json()
        assert not any(item["kind"] == "hub" and item["project_id"] == "am" for item in after_hub)

        approved = client.post(
            "/project/pc1/jarvis/command",
            data={"line": "approve 1", "return_to": "/inbox"},
            follow_redirects=True,
        )
        assert approved.status_code == 200
        after_jj = client.get("/api/inbox").json()
        assert not any(item["kind"] == "jj-approval" for item in after_jj)

        leftover = collect_inbox(
            [{"id": "academy", "pc": "pc1", "state": "blocked", "title": "Academy", "task": "needs a key", "note": "", "blocker": "missing token", "reason": ""}],
            {"project_dashboards": {}},
        )
        assert leftover[0]["kind"] == "hub"
        assert leftover[0]["state"] == "blocked"
