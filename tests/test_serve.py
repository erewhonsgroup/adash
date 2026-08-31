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
