"""Needs-Joshua aggregation: hub review/blocked plus JJ pending approvals."""

from __future__ import annotations

from typing import Any, Iterable

from adash.dashboards import spec_for
from adash.dashboards.jj import snapshot as jj_snapshot

HUB_NEEDS = frozenset({"review", "blocked"})


def as_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return dict(row)


def hub_needs_you(state: str) -> bool:
    return (state or "").lower() in HUB_NEEDS


def jj_pending_counts(fleet: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    mapping = fleet.get("project_dashboards") or {}
    for project_id, spec in mapping.items():
        if not isinstance(spec, dict) or spec.get("kind") != "jj":
            continue
        snap = jj_snapshot(spec)
        counts[str(project_id)] = len(snap.get("inbox") or [])
    return counts


def annotate_needs_you(
    projects: Iterable[Any],
    fleet: dict[str, Any],
    pending: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    pending = pending if pending is not None else jj_pending_counts(fleet)
    annotated: list[dict[str, Any]] = []
    for row in projects:
        item = as_dict(row)
        item["needs_you"] = hub_needs_you(str(item.get("state") or "")) or pending.get(
            str(item.get("id") or ""), 0
        ) > 0
        annotated.append(item)
    return annotated


def collect_inbox(projects: Iterable[Any], fleet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [as_dict(row) for row in projects]
    items: list[dict[str, Any]] = []
    pc_by_id = {str(row.get("id") or ""): str(row.get("pc") or "") for row in rows}
    for row in rows:
        if not hub_needs_you(str(row.get("state") or "")):
            continue
        items.append(
            {
                "kind": "hub",
                "key": f"hub:{row.get('pc')}:{row.get('id')}",
                "pc": row.get("pc") or "",
                "project_id": row.get("id") or "",
                "title": row.get("title") or row.get("id") or "",
                "state": row.get("state") or "",
                "task": row.get("task") or "",
                "note": row.get("note") or "",
                "subject": "",
                "reason": row.get("blocker") or row.get("reason") or "",
                "approval_id": None,
            }
        )
    mapping = fleet.get("project_dashboards") or {}
    for project_id, spec in mapping.items():
        if not isinstance(spec, dict) or spec.get("kind") != "jj":
            continue
        snap = jj_snapshot(spec)
        pc = pc_by_id.get(str(project_id)) or "pc1"
        for approval in snap.get("inbox") or []:
            kind = approval.get("kind") or "approval"
            subject = approval.get("subject") or ""
            items.append(
                {
                    "kind": "jj-approval",
                    "key": f"jj:{project_id}:{approval.get('id')}",
                    "pc": pc,
                    "project_id": str(project_id),
                    "title": f"{kind} · {subject}".strip(" ·"),
                    "state": "pending",
                    "task": "",
                    "note": approval.get("reason") or "",
                    "subject": subject,
                    "reason": approval.get("reason") or "",
                    "approval_id": approval.get("id"),
                }
            )
    return items


def safe_return(path: str, fallback: str) -> str:
    raw = (path or "").strip()
    if not raw.startswith("/") or raw.startswith("//") or "\\" in raw or "://" in raw:
        return fallback
    if raw in {"/", "/inbox"} or raw.startswith("/project/"):
        return raw
    return fallback


def jj_spec_for(fleet: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    spec = spec_for(fleet, project_id)
    if spec and spec.get("kind") == "jj":
        return spec
    return None
