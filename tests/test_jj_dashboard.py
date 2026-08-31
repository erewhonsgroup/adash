from __future__ import annotations

from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adash.dashboards.jj import parse_command
from adash.serve import create_app
from conftest import make_am_root, write_fleet

JJ_ROOT = Path(r"C:\ALLU\projects\Jarvis")
pytestmark = pytest.mark.skipif(
    not (JJ_ROOT / "jj" / "cockpit.py").is_file(),
    reason="JJ kernel is not at C:\\ALLU\\projects\\Jarvis",
)


def test_parse_command():
    assert parse_command(":approve 3") == ("approval.approve", {"id": 3})
    assert parse_command("task add P19 git-diff scope") == (
        "task.add",
        {"title": "P19 git-diff scope"},
    )
    assert parse_command("task done 5") == ("task.done", {"id": 5})
    with pytest.raises(ValueError):
        parse_command("launch the missiles")


def _seed_jj(db: Path) -> None:
    import sys

    if str(JJ_ROOT) not in sys.path:
        sys.path.insert(0, str(JJ_ROOT))
    from jj.approvals import ApprovalStore
    from jj.ledger import Ledger
    from jj.tasks import TaskStore

    with closing(Ledger(db)) as ledger:
        TaskStore(ledger).add_task("P19: git-diff scope verification")
        ApprovalStore(ledger).request("tool", "codex", "needs a grant")


def test_jj_deck_reads_kernel_and_runs_commands(tmp_path, monkeypatch):
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
        page = client.get("/project/pc1/jarvis")
        assert page.status_code == 200
        assert "JJ command deck" in page.text
        assert "P19: git-diff scope verification" in page.text
        assert "codex" in page.text
        board = client.get("/")
        assert "deck" in board.text
        done = client.post(
            "/project/pc1/jarvis/command",
            data={"line": "task done 1"},
            follow_redirects=True,
        )
        assert done.status_code == 200
        assert "task 1 done" in done.text
        kernel = client.get("/api/project/pc1/jarvis/kernel").json()
        assert kernel["ok"] is True
        assert kernel["open_tasks"] == []
        assert any(t["id"] == 1 and t["status"] == "done" for t in kernel["tasks"])
        approved = client.post(
            "/project/pc1/jarvis/command",
            data={"line": ":approve 1"},
            follow_redirects=True,
        )
        assert approved.status_code == 200
        inbox = client.get("/api/project/pc1/jarvis/kernel").json()["inbox"]
        assert inbox == []
