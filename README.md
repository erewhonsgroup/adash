# ADash

Central hub and SQLite database for the fleet control-center dashboard.

ADash is the new home for **all-project inventory, live work state, and the browser board**. `C:\AM` stays the PowerShell launcher and check-in shim until that cutover is explicit. Markdown remains human truth; this database is the query spine the dashboard reads.

## Why

`C:\AM` grew into a mixed control-center plus a pile of unrelated work. ADash keeps the hub on `D:\` with one job: know every tracked project, rank what needs attention, and serve that board from a local SQLite database.

## Quickstart

From `D:\ADash` (system Python, no venv):

```powershell
pip install -r requirements.txt
python -m pytest -q
python -m adash ingest
python -m adash status
python -m adash serve
```

Then open `http://127.0.0.1:8788/`. Health check: `http://127.0.0.1:8788/healthz`.

Jarvis/JJ has a custom command deck at `http://127.0.0.1:8788/project/pc1/jarvis`. It reads the JJ kernel at `C:\ALLU\projects\Jarvis` (`~\.jj\ledger.db`) and runs the same audited verbs as `python -m jj`.

Research for the next dashboard work (agent control planes vs AI OS vs observability): `docs/DASHBOARD_RESEARCH.md`.

Re-ingest from the board or:

```powershell
python -m adash ingest
```

Check in this hub:

```powershell
python -m adash checkin --id adash --state working --task "what you are doing"
```

## What it stores

| Table | Role |
| --- | --- |
| `pcs` | Fleet machines (`pc1` JESUSISKING … `pc5` ThankYouJesus) |
| `projects` | One row per project id + PC: path, state, attention, purpose |
| `events` | Append-only hub events (ingest, state writes, check-ins) |
| `meta` | Last ingest time and counts |

Database file: `data/adash.db` (gitignored). Schema: `schema.sql`.

Ingest sources, in order:

1. `C:\AM\scripts\AM.Sessions*.ps1` (PC-segmented session registries)
2. Extra scan roots in `config/fleet.json` (`C:\ALLU\projects`, `C:\ACLC\projects`, `D:\Projects`)
3. Latest rows from `C:\AM\brain\central-am.db` (read-only)
4. Local `C:\AM\state\*.json` when newer than the event overlay
5. Cheap on-disk probes (exists / `.git` present). No `git status` on ingest.

## Commands

| Command | Purpose |
| --- | --- |
| `python -m adash ingest` | Rebuild hub rows from AM + scan roots |
| `python -m adash status` | Attention-sorted CLI board |
| `python -m adash serve` | Dashboard on `127.0.0.1:8788` |
| `python -m adash checkin --id <id> --state working` | Write state into the hub |
| `.\scripts\Serve-ADash.ps1` | ingest then serve |
| `.\scripts\Ingest-ADash.ps1` | ingest only |

## Layout

```
adash/           Python package (db, ingest, attention, dashboard)
config/fleet.json
schema.sql
tests/
scripts/
data/            local SQLite (ignored)
```

## Status

v0.1 — hub database, ingest, fleet board, project detail, hub-local state writes. AM launchers and `Set-AMStatus.ps1` are unchanged. ADash does not write AM state files yet.

## Boundaries

- No secrets in this repo.
- Do not sync the live SQLite file across PCs.
- Do not hardcode a Windows username; use `%USERPROFILE%` / `~`.
- Main PC (`JESUSISKING`) is the writer for the hub database.
