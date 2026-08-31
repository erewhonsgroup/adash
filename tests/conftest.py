from __future__ import annotations

import json
from pathlib import Path

import pytest

from adash.db import connect, init_db


SAMPLE_SESSIONS = """
. "$PSScriptRoot\\AM.Sessions.Common.ps1"

$AMSessions = @(
  New-AMSession -Id 'am' -Title 'AM codex' -Folder 'C:\\AM' -Group @('infra', 'pc1')
  New-AMSession -Id 'adash' -Title 'ADash' -Folder 'D:\\ADash' -Command 'python' -Group @('infra', 'hub', 'pc1')
  New-AMSession -Id 'academy' -Title 'Academy claude' -Folder 'C:\\ALLU\\projects\\academy' -Command 'claude' -Group 'pc1'
)
"""


def write_fleet(tmp_path: Path, am_root: Path, scan_root: Path | None = None) -> Path:
    fleet = {
        "schema_version": "adash.fleet.v1",
        "listen_host": "127.0.0.1",
        "listen_port": 8788,
        "am_root": str(am_root),
        "am_central_db": str(am_root / "brain" / "central-am.db"),
        "am_state_dir": str(am_root / "state"),
        "scan_roots": [str(scan_root)] if scan_root else [],
        "pcs": [
            {"id": "pc1", "hostname": "JESUSISKING", "role": "main"},
            {"id": "pc2", "hostname": "PRAISEJESUS", "role": "satellite"},
        ],
    }
    path = tmp_path / "fleet.json"
    path.write_text(json.dumps(fleet), encoding="utf-8")
    return path


def make_am_root(tmp_path: Path) -> Path:
    am_root = tmp_path / "AM"
    scripts = am_root / "scripts"
    scripts.mkdir(parents=True)
    (am_root / "state").mkdir()
    (am_root / "brain").mkdir()
    (scripts / "AM.Sessions.ps1").write_text(SAMPLE_SESSIONS, encoding="utf-8")
    (scripts / "AM.Sessions.Common.ps1").write_text("", encoding="utf-8")
    (am_root / "state" / "am.json").write_text(
        json.dumps(
            {
                "Id": "am",
                "State": "working",
                "Task": "keep the fleet honest",
                "Note": "",
                "Updated": "2026-08-31 12:00:00",
            }
        ),
        encoding="utf-8",
    )
    return am_root


@pytest.fixture
def am_root(tmp_path: Path) -> Path:
    return make_am_root(tmp_path)


@pytest.fixture
def fleet_file(tmp_path: Path, am_root: Path) -> Path:
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "BrandNew").mkdir()
    (scan / "BrandNew" / "README.md").write_text("# Brand New\nA scanned extra project.\n", encoding="utf-8")
    return write_fleet(tmp_path, am_root, scan)


@pytest.fixture
def db_conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "adash.db"
    monkeypatch.setenv("ADASH_DB", str(db))
    conn = connect(db, write=True)
    init_db(conn)
    yield conn
    conn.close()
