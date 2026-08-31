# CLAUDE.md

ADash is the new central hub (`D:\ADash`) for the fleet control-center dashboard and its SQLite database.

## Run / test / build

```powershell
pip install -r requirements.txt
python -m pytest -q
python -m adash ingest
python -m adash serve
```

- Entry point: `python -m adash`
- Tests: `python -m pytest -q`
- DB: `data/adash.db` (gitignored), schema in `schema.sql`
- Config: `config/fleet.json`
- Port: `8788` so it can coexist with AM on `8787`

## Layout

- `adash/attention.py` — AM-compatible attention scores
- `adash/registry.py` — parse `New-AMSession` lines; scan extra roots
- `adash/ingest.py` — merge registry + AM state + central events + disk probe into SQLite
- `adash/db.py` — schema init and queries
- `adash/serve.py` — FastAPI board
- `adash/templates/` — Jinja board and project pages

## Conventions

- System Python, no venv.
- Surgical diffs. Do not import AM's dashboard package or its uv project.
- Ingest is the write path; request handlers read SQLite.
- No secrets. No live DB in git.
- Username-free paths.

## Gotchas

- `Set-AMStatus.ps1 -Here` will not match `D:\ADash` until AM grows a session row. Use `python -m adash checkin` here.
- Ingest overlays PC1 `C:\AM\state\*.json` onto local rows only. Other PCs get latest central-DB events when that file is present.
- Folder existence is probed; `git status` is not. `git_dirty` is `missing`, `not-git`, or empty.
