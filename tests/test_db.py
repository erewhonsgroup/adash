from adash.db import get_project, list_projects, upsert_project


def test_upsert_and_filter(db_conn):
    upsert_project(
        db_conn,
        {
            "id": "alpha",
            "pc": "pc1",
            "title": "Alpha",
            "path": "D:\\Alpha",
            "state": "working",
            "attention_score": 40,
            "attention": "working",
            "ingested_at": "2026-08-31 12:00:00",
        },
    )
    upsert_project(
        db_conn,
        {
            "id": "beta",
            "pc": "pc2",
            "title": "Beta",
            "path": "C:\\Beta",
            "state": "idle",
            "attention_score": 100,
            "attention": "idle",
            "ingested_at": "2026-08-31 12:00:00",
        },
    )
    db_conn.commit()
    assert get_project(db_conn, "alpha", "pc1")["title"] == "Alpha"
    only_pc2 = list_projects(db_conn, pc="pc2")
    assert [row["id"] for row in only_pc2] == ["beta"]
    working = list_projects(db_conn, state="working")
    assert [row["id"] for row in working] == ["alpha"]
