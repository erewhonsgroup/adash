from pathlib import Path

from adash.registry import parse_session_args, parse_sessions_file, slug


def test_parse_grouped_session():
    parsed = parse_session_args(
        "-Id 'am' -Title 'AM codex' -Folder 'C:\\AM' -Group @('infra', 'pc1')"
    )
    assert parsed is not None
    assert parsed["id"] == "am"
    assert parsed["path"] == "C:\\AM"
    assert parsed["groups"] == ["infra", "pc1"]


def test_parse_command_and_single_group():
    parsed = parse_session_args(
        "-Id 'academy' -Title 'Academy claude' -Folder 'C:\\ALLU\\projects\\academy' -Command 'claude' -Group 'pc1'"
    )
    assert parsed is not None
    assert parsed["command"] == "claude"
    assert parsed["groups"] == ["pc1"]


def test_parse_sessions_file(tmp_path: Path):
    path = tmp_path / "AM.Sessions.PC2.ps1"
    path.write_text(
        "New-AMSession -Id 'susie' -Title 'Susie' -Folder 'C:\\Susie' -Group 'pc2'\n",
        encoding="utf-8",
    )
    rows = parse_sessions_file(path)
    assert len(rows) == 1
    assert rows[0]["pc"] == "pc2"
    assert rows[0]["id"] == "susie"


def test_slug():
    assert slug("Brand New") == "brand-new"


def test_live_am_registry_if_present():
    root = Path(r"C:\AM\scripts")
    if not (root / "AM.Sessions.ps1").is_file():
        return
    rows = parse_sessions_file(root / "AM.Sessions.ps1")
    assert len(rows) >= 70
    assert any(row["id"] == "am" for row in rows)
