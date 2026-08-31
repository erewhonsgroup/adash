# Lessons

- `Set-AMStatus.ps1 -Here` matches AM session folders only. `D:\ADash` is not in `AM.Sessions.ps1`, so AM check-in throws until that registry gains a row. Use `python -m adash checkin` for this repo.
- Do not report AM's reason for tracking a folder as the project purpose. Prefer the project's own README/docs.
- Desk PCs use two Windows account roles. `josh` is remoting/admin; the desktop user owns Grok/Claude/Codex state.
- Reference machines by PC name (`JESUSISKING`, …), never by the logged-in username.
- ADash must not copy `C:\AM`'s unrelated trees. The hub is inventory + dashboard + SQLite, not a dump of AM.
