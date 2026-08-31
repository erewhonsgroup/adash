from __future__ import annotations

from typing import Any


def spec_for(fleet: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    mapping = fleet.get("project_dashboards") or {}
    spec = mapping.get(project_id)
    if not isinstance(spec, dict):
        return None
    return spec


def custom_ids(fleet: dict[str, Any]) -> set[str]:
    mapping = fleet.get("project_dashboards") or {}
    return {str(key) for key in mapping}
