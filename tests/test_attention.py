from adash.attention import score_attention


def test_review_dirty_is_highest_priority():
    score, label, reason = score_attention("review", "yes", "", "", "")
    assert (score, label) == (0, "review-dirty")
    assert "review" in reason


def test_blocked_beats_queued():
    blocked = score_attention("blocked", "", "", "", "")
    queued = score_attention("queued", "", "", "", "")
    assert blocked[0] < queued[0]
    assert blocked[1] == "blocked"
    assert queued[1] == "queued"


def test_missing_folder_escalates_idle():
    score, label, _ = score_attention("idle", "missing", "", "", "")
    assert (score, label) == (15, "missing")


def test_working_stale():
    score, label, _ = score_attention(
        "working",
        "",
        "",
        "",
        "2020-01-01 00:00:00",
        stale_minutes=120,
    )
    assert (score, label) == (20, "stale")


def test_noted_idle():
    score, label, _ = score_attention("idle", "", "do the thing", "", "")
    assert (score, label) == (50, "noted")
