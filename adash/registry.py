from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SESSION_LINE = re.compile(r"New-AMSession\s+(?P<args>.+)$")
FLAG = re.compile(
    r"-(?P<name>Id|Title|Folder|Command|Group)\s+(?P<value>@\([^)]*\)|'[^']*'|\"[^\"]*\")",
    re.IGNORECASE,
)
FILE_PC = re.compile(r"AM\.Sessions(?:\.PC(\d+))?\.ps1$", re.IGNORECASE)


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_group(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("@(") and raw.endswith(")"):
        inner = raw[2:-1]
        found = re.findall(r"'([^']*)'|\"([^\"]*)\"", inner)
        values = [a or b for a, b in found]
        return [item.strip() for item in values if item.strip()]
    single = strip_quotes(raw).strip()
    return [single] if single else []


def parse_session_args(arg_str: str) -> dict[str, Any] | None:
    flags: dict[str, str] = {}
    for match in FLAG.finditer(arg_str):
        flags[match.group("name").lower()] = match.group("value")
    session_id = strip_quotes(flags.get("id", "")).strip()
    folder = strip_quotes(flags.get("folder", "")).strip()
    if not session_id or not folder:
        return None
    groups = parse_group(flags["group"]) if "group" in flags else ["default"]
    command = strip_quotes(flags.get("command", "")).strip() or "codex"
    title = strip_quotes(flags.get("title", "")).strip() or session_id
    return {
        "id": session_id,
        "title": title,
        "path": folder,
        "command": command,
        "groups": groups,
    }


def pc_from_filename(path: Path) -> str:
    match = FILE_PC.search(path.name)
    if not match:
        return "pc1"
    number = match.group(1)
    return f"pc{number}" if number else "pc1"


def pc_from_groups(groups: list[str], fallback: str) -> str:
    for group in groups:
        lowered = group.strip().lower()
        if re.fullmatch(r"pc[1-9]", lowered):
            return lowered
    return fallback


def parse_sessions_file(path: Path) -> list[dict[str, Any]]:
    file_pc = pc_from_filename(path)
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = SESSION_LINE.search(line)
        if not match:
            continue
        parsed = parse_session_args(match.group("args"))
        if not parsed:
            continue
        parsed["pc"] = pc_from_groups(parsed["groups"], file_pc)
        parsed["source"] = "am-session"
        parsed["registry_file"] = path.name
        rows.append(parsed)
    return rows


def discover_session_files(am_root: Path) -> list[Path]:
    scripts = am_root / "scripts"
    if not scripts.is_dir():
        return []
    files = []
    for path in sorted(scripts.glob("AM.Sessions*.ps1")):
        if "Common" in path.name:
            continue
        files.append(path)
    return files


def parse_am_sessions(am_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in discover_session_files(am_root):
        rows.extend(parse_sessions_file(path))
    return rows


def slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return text or "project"


def read_purpose(folder: Path) -> str:
    for name in ("README.md", "AGENTS.md", "CLAUDE.md", "PROJECT.md"):
        path = folder / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        heading = ""
        for line in text.splitlines():
            raw = line.strip()
            if not raw:
                continue
            if raw.startswith("#"):
                if not heading:
                    heading = raw.lstrip("#").strip()
                continue
            return raw[:240]
        if heading:
            return heading[:240]
    return ""


def probe_path(folder: str) -> dict[str, Any]:
    path = Path(folder)
    exists = path.exists()
    git_dir = path / ".git"
    is_git = exists and git_dir.exists()
    if not exists:
        dirty = "missing"
    elif is_git:
        dirty = ""
    else:
        dirty = "not-git"
    return {
        "exists_on_disk": 1 if exists else 0,
        "is_git": 1 if is_git else 0,
        "git_dirty": dirty,
    }


def load_am_state_file(state_dir: Path, session_id: str) -> dict[str, Any] | None:
    path = state_dir / f"{session_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def scan_project_root(root: Path, pc: str) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    try:
        children = sorted(root.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return []
    for child in children:
        if not child.is_dir() or child.name.startswith("."):
            continue
        rows.append(
            {
                "id": slug(child.name),
                "title": child.name,
                "path": str(child),
                "command": "",
                "groups": ["scan", pc],
                "pc": pc,
                "source": "scan",
                "purpose": read_purpose(child),
            }
        )
    return rows
