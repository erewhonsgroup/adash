import pytest
from fastapi.testclient import TestClient

from adash.serve import create_app


def test_healthz_and_board(tmp_path, fleet_file, monkeypatch):
    monkeypatch.setenv("ADASH_FLEET", str(fleet_file))
    monkeypatch.setenv("ADASH_DB", str(tmp_path / "adash.db"))
    with TestClient(create_app()) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        body = health.json()
        assert body["status"] == "ok"
        assert body["projects"] >= 3
        page = client.get("/")
        assert page.status_code == 200
        assert "ADash" in page.text
        assert 'href="/project/pc1/am"' in page.text


def test_state_write(tmp_path, fleet_file, monkeypatch):
    monkeypatch.setenv("ADASH_FLEET", str(fleet_file))
    monkeypatch.setenv("ADASH_DB", str(tmp_path / "adash.db"))
    with TestClient(create_app()) as client:
        response = client.post(
            "/project/pc1/am/state",
            data={"state": "review", "task": "check the hub", "note": "tests green", "blocker": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "check the hub" in response.text
        assert "review" in response.text
        payload = client.get("/api/projects", params={"q": "am"}).json()
        match = [row for row in payload if row["id"] == "am" and row["pc"] == "pc1"][0]
        assert match["state"] == "review"
        assert match["task"] == "check the hub"


def test_handler_closes_connection_when_a_query_fails(tmp_path, fleet_file, monkeypatch):
    """A failing query must not strand an open SQLite handle (locks the hub DB)."""
    import sqlite3

    from adash import serve as serve_mod

    monkeypatch.setenv("ADASH_FLEET", str(fleet_file))
    monkeypatch.setenv("ADASH_DB", str(tmp_path / "adash.db"))

    class TrackedConnection:
        def __init__(self, conn):
            self._conn = conn
            self.closed = False

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def close(self):
            self.closed = True
            self._conn.close()

    opened = []
    real_connect = serve_mod.connect

    def tracking_connect(*args, **kwargs):
        conn = TrackedConnection(real_connect(*args, **kwargs))
        opened.append(conn)
        return conn

    monkeypatch.setattr(serve_mod, "connect", tracking_connect)
    app = create_app()

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(serve_mod, "list_projects", boom)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/projects").status_code == 500

    assert opened, "handler never opened a connection"
    assert all(conn.closed for conn in opened), "a failing request leaked an open connection"
