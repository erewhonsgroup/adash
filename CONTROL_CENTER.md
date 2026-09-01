# ADash Control Center

ADash is the local hub for LLM-assisted work across the Windows fleet, rebuilt as a SQLite-backed dashboard instead of a PowerShell table loop sitting inside `C:\AM`.

## Mandate

ADash should coordinate:

- A single inventory of projects across PCs, not only AM-tracked folders.
- Live work state (`idle`, `queued`, `working`, `review`, `blocked`, `done`) and attention rank.
- A browser control board plus a CLI status view, both reading the same database.
- Durable event history for hub writes (ingest, check-in, dashboard state changes).
- Pointers at downstream repos. ADash is not the source repository for those projects.

`C:\AM` keeps session launchers, hardcoded PowerShell registries, and `Set-AMStatus.ps1` until an explicit cutover. ADash imports those registries; it does not replace them on day one.

## Layers

1. **Hub database** — `data/adash.db`, schema in `schema.sql`. This is the query spine. Generated and gitignored.

2. **Human truth** — `CONTROL_CENTER.md`, `AGENTS.md`, `tasks/lessons.md`, and downstream project READMEs. Markdown wins when SQLite and docs disagree about purpose.

3. **Ingest** — `python -m adash ingest` rebuilds project rows from AM session files, configured scan roots, read-only central AM events, and local AM state files.

4. **Board** — FastAPI app on `127.0.0.1:8788`. Request handlers do not call git. Re-ingest to refresh. Project ids listed in `config/fleet.json` `project_dashboards` get a custom deck instead of the generic project page. First: `jarvis` → JJ command deck (reads `C:\ALLU\projects\Jarvis`, does not copy the kernel). Survey of 2026 agent-orchestration / AI-OS / command-center UIs: `docs/DASHBOARD_RESEARCH.md`.

5. **Check-in** — `python -m adash checkin` writes hub state without touching AM's SMB push path.

## Boundaries

- Windows-first. PowerShell wrappers are thin; the hub is Python.
- Main PC (`JESUSISKING`) is the sole writer of the hub database.
- Do not sync the live SQLite file. Sync event/export batches later if satellites need a copy.
- Do not store secrets, tokens, or provider credentials here.
- Keep PC identity in `config/fleet.json` hostnames, never in a logged-in username.
- Preserve stable AM session IDs when importing AM registries.
- Do not treat "appears in the dashboard" as a project's purpose. Prefer that project's README.
- Dashboard references and optional deps: OSI-open or fully free self-host only. No paid feature gates. See `docs/DASHBOARD_RESEARCH.md` §0.

## Relationship to AM

| Concern | Lives in |
| --- | --- |
| Session launch tabs | `C:\AM` PowerShell registries |
| Status shim used by existing agent instructions | `C:\AM\Set-AMStatus.ps1` |
| Event batches / `central-am.db` | `C:\AM` / `C:\AMBrainDrop` (read-only to ADash) |
| All-project inventory + attention board + hub DB | `D:\ADash` |

Cutover of check-ins and launchers onto ADash is a later phase, not implied by this repo existing.
