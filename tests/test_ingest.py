from adash.db import connect, init_db, list_projects
from adash.ingest import ingest
from adash.paths import load_fleet


def test_ingest_merges_registry_state_and_scan(tmp_path, fleet_file, monkeypatch):
    monkeypatch.setenv("ADASH_FLEET", str(fleet_file))
    monkeypatch.setenv("ADASH_DB", str(tmp_path / "adash.db"))
    conn = connect(write=True)
    init_db(conn)
    result = ingest(conn, load_fleet())
    rows = { (row["id"], row["pc"]): dict(row) for row in list_projects(conn) }
    conn.close()
    assert result["count"] >= 4
    am = rows[("am", "pc1")]
    assert am["state"] == "working"
    assert am["task"] == "keep the fleet honest"
    assert am["attention"] == "stale" or am["attention"] == "working"
    assert ("brandnew", "pc1") in rows
    assert "scanned extra project" in rows[("brandnew", "pc1")]["purpose"].lower()
    assert ("adash", "pc1") in rows


def test_ingest_keeps_newer_hub_checkin(tmp_path, fleet_file, monkeypatch):
    monkeypatch.setenv("ADASH_FLEET", str(fleet_file))
    monkeypatch.setenv("ADASH_DB", str(tmp_path / "adash.db"))
    conn = connect(write=True)
    init_db(conn)
    ingest(conn, load_fleet())
    from adash.attention import score_attention
    from adash.db import get_project, upsert_project

    current = dict(get_project(conn, "am", "pc1"))
    current["state"] = "review"
    current["task"] = "hub wrote this"
    current["note"] = "do not clobber"
    current["updated_at"] = "2099-01-01 00:00:00"
    score, label, reason = score_attention("review", str(current.get("git_dirty") or ""), current["task"], current["note"], current["updated_at"])
    current["attention_score"] = score
    current["attention"] = label
    current["reason"] = reason
    upsert_project(conn, current)
    conn.commit()
    ingest(conn, load_fleet())
    row = dict(get_project(conn, "am", "pc1"))
    conn.close()
    assert row["state"] == "review"
    assert row["task"] == "hub wrote this"
