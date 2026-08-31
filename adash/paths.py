from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCHEMA_PATH = ROOT / "schema.sql"
FLEET_PATH = ROOT / "config" / "fleet.json"
DEFAULT_DB = DATA_DIR / "adash.db"

VALID_STATES = ("idle", "queued", "working", "review", "blocked", "done")


def db_path() -> Path:
    raw = os.environ.get("ADASH_DB")
    return Path(raw) if raw else DEFAULT_DB


def fleet_path() -> Path:
    raw = os.environ.get("ADASH_FLEET")
    return Path(raw) if raw else FLEET_PATH


def load_fleet(path: Path | None = None) -> dict[str, Any]:
    target = path or fleet_path()
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fleet config is not an object: {target}")
    return data


def local_pc_id(fleet: dict[str, Any] | None = None) -> str:
    cfg = fleet if fleet is not None else load_fleet()
    hostname = socket.gethostname()
    for pc in cfg.get("pcs", []):
        if str(pc.get("hostname", "")).lower() == hostname.lower():
            return str(pc["id"])
    return "pc1"


def now_stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
