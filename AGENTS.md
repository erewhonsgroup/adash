# AGENTS.md

## Project Role

`D:\ADash` is the central hub and SQLite database for the fleet control-center dashboard. It inventories every tracked project, ranks attention, and serves the board. `C:\AM` remains the PowerShell launcher and status shim until an explicit cutover.

Read first:

- `CONTROL_CENTER.md`
- `README.md`
- `tasks\lessons.md`

## Workflow

- Keep this repo the hub: schema, ingest, dashboard, project rows. Do not copy `C:\AM`'s unrelated trees (raw captures, prizepicks, Sysinternals, bloated `state\`) into ADash.
- System Python only. No venv, uv, or lockfile unless the operator asks.
- Dashboard reads SQLite. Refresh data with `python -m adash ingest`, not per-request git probes.
- Preserve AM session IDs and states: `idle`, `queued`, `working`, `review`, `blocked`, `done`.
- Keep PC registries segmented at the AM source (`scripts\AM.Sessions.PC*.ps1`). ADash imports them; it does not own those files.
- Do not commit `data\`, secrets, tokens, or live databases.
- Never hardcode a Windows username in a path.

## Windows Desk Account Model

- `josh` is the shared local administrator/remoting account. It is not the logged-in desktop user.
- User-scoped state (Grok, Claude, Codex, Credential Manager, npm, PATH, `%APPDATA%`) lives on the desktop user that actually runs those apps.
- Reference machines by PC name: PC1 `JESUSISKING`, PC2 `PRAISEJESUS`, PC3 `HAILKINGJESUS`, PC4 `JESUSISLORD`, PC5 `ThankYouJesus`.

## Commands

```powershell
python -m pytest -q
python -m adash ingest
python -m adash status
python -m adash serve
python -m adash checkin --id adash --state working --task "<short task>"
```

Dashboard: `http://127.0.0.1:8788/` (AM's board stays on `8787` until cutover).

## Check-ins

This project tracks itself in the ADash hub:

```powershell
python -m adash checkin --id adash --state working --task "<short task>"
python -m adash checkin --id adash --state review --note "<summary and checks>"
python -m adash checkin --id adash --state done --note "<final summary>"
```
