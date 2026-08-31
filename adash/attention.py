from __future__ import annotations

from datetime import datetime


def age_minutes(updated: str, now: datetime | None = None) -> int | None:
    if not updated or not updated.strip():
        return None
    try:
        parsed = datetime.strptime(updated.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    current = now or datetime.now()
    return int((current - parsed).total_seconds() // 60)


def score_attention(
    state: str,
    dirty: str,
    task: str = "",
    note: str = "",
    updated: str = "",
    stale_minutes: int = 120,
    now: datetime | None = None,
) -> tuple[int, str, str]:
    """Port of AM Get-AMAttention so operators keep the same labels."""
    score = 100
    label = "idle"
    reason = ""
    state = (state or "idle").strip().lower()
    dirty = (dirty or "").strip().lower()
    task = task or ""
    note = note or ""

    if state == "review":
        if dirty == "yes":
            score, label, reason = 0, "review-dirty", "review has local changes"
        elif dirty == "not-git":
            score, label, reason = 8, "review-nonrepo", "review for non-git folder"
        else:
            score, label, reason = 5, "review", "ready for human review"
    elif state == "blocked":
        score, label, reason = 10, "blocked", "needs input or recovery"
    elif state == "queued":
        score, label, reason = 30, "queued", "ready to start"
    elif state == "working":
        age = age_minutes(updated, now=now)
        if age is not None and age >= stale_minutes:
            score, label, reason = 20, "stale", f"working for {age}m"
        elif dirty == "yes":
            score, label, reason = 35, "dirty-working", "working repo has local changes"
        elif dirty == "not-git":
            score, label, reason = 65, "working-nonrepo", "working in non-git folder"
        else:
            score, label, reason = 40, "working", "in progress"
    elif state == "done":
        score, label, reason = 70, "done", "completed status is still set"

    if dirty == "missing" and score > 15:
        score, label, reason = 15, "missing", "folder does not exist"
    elif dirty == "yes" and score > 35:
        score, label, reason = 35, "dirty", "repository has local changes"
    elif dirty == "not-git" and score > 80:
        score, label, reason = 80, "nonrepo", "folder is not a git repository"

    if label == "idle" and (task.strip() or note.strip()):
        score, label, reason = 50, "noted", "task or note exists"

    return score, label, reason
