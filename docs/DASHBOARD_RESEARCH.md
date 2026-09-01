# Dashboard research — agent orchestration, AI OS, and command-center UX

Written 2026-08-31 for ADash / JJ. Purpose: decide what the hub should look like and which primitives to steal. Not a shopping list.

Sources were checked the same day. Licences, star counts, and product claims move fast; treat product rows as a snapshot.

## 0. Hard filter — open source / free only

Operator rule (2026-08-31): **OSI-open or fully free self-host. No product whose useful fleet/inbox/trace/worktree features sit behind a paid SKU.**

Allowed to *steal UX from* or optionally run:

| Thing | Licence | Notes |
| --- | --- | --- |
| ADash, JJ | MIT (ours) | Hub + kernel |
| [Orca](https://github.com/stablyai/orca) | MIT | ADE; steal Needs-You kanban, not adopt as ADash |
| [Emdash](https://github.com/generalaction/emdash) | Apache-2.0 | Local-first; steal worktree compare |
| [Claude Squad](https://github.com/smtg-ai/claude-squad) | AGPL-3.0 | Copyleft; terminal worktrees. Fine to read; do not vend into ADash without AGPL implications |
| [langchain-ai/agent-inbox](https://github.com/langchain-ai/agent-inbox) | MIT | HITL inbox UX |
| [LangGraph](https://github.com/langchain-ai/langgraph) OSS | MIT | Runtime, not a dashboard. Do not make it the board |
| [Langfuse](https://github.com/langfuse/langfuse) self-host | MIT core | Product features (traces, annotation, playground) MIT. `/ee` is SCIM / extra audit / retention — we will not use those; if we need audit, ADash events already do it |
| [12-factor-agents](https://github.com/humanlayer/12-factor-agents) | Apache-2.0 code, CC BY-SA content | Doctrine |
| Grok `/dashboard` | already installed | Deep-link live sessions; not a purchase |
| OpenHands | Apache-2.0 / MIT (project OSS) | Event-loop pattern |

Disqualified (paid gate, source-available-not-OSI, or cloud-only useful bits):

| Thing | Why out |
| --- | --- |
| Nimbalyst Teams | MIT app, but Teams is $20/user/mo for the collaboration layer. Paid push for features. |
| Conductor | Proprietary, macOS |
| Superset ADE | Elastic License 2.0 — not OSI. Paid seats |
| Warp (terminal/cloud agents) | Free terminal; fleet/cloud agents on paid tiers |
| LangSmith | Closed SaaS. LangGraph OSS is fine; Smith is not |
| CrewAI Enterprise tracing/RBAC | OSS crew framework ≠ paid enterprise board |
| Bedrock AgentCore, Codex App as control plane | Vendor runtime / single-engine proprietary |
| Langfuse Cloud / Langfuse `/ee` | Same product, paid modules. Self-host MIT only, or skip |
| OpenClawHQ Mission Control writeups | Vendor dashboard packaging; prefer the OSS [openclaw-mission-control](https://github.com/abhi1693/openclaw-mission-control) repo if we look at OpenClaw at all |

Steal means copy a *pattern* into ADash (MIT). It does not mean depend on their hosted app.

## 1. The split that matters

“Agent orchestration dashboard” names two products that do not substitute for each other ([Nimbalyst comparison, Aug 2026](https://nimbalyst.com/blog/best-ai-agent-orchestration-platforms-2026/)):

| Market | Operator | Unit of work | Success | Typical stack |
| --- | --- | --- | --- | --- |
| **Workflow / AI OS runtime** | The application | A graph, crew, or always-on agent | Throughput, cost, error rate, durable resume | LangGraph, CrewAI, Microsoft Agent Framework, Bedrock AgentCore, OpenClaw |
| **Coding-agent control plane** | A human at a keyboard | A task assigned to Claude/Codex/Grok | How much work one person can *supervise* before review breaks | Orca (MIT), Emdash (Apache-2.0), Claude Squad (AGPL), Grok dashboard (already here) |

ADash is the second, plus a **fleet/project inventory** AM already tracked. JJ is the first (a private kernel). Putting LangGraph or CrewAI under the fleet board would buy a library when the missing piece is a workspace. The reverse is equally true: Orca will not be AM Brain.

HumanLayer’s [12-factor agents](https://github.com/humanlayer/12-factor-agents) (25.6k stars in the Aug 31 orchestration ranking) is the design doctrine for the kernel side: own prompts, own context, own control flow, launch/pause/resume as APIs, contact humans *as a tool*, small focused agents. Most production founders they interviewed rolled the stack themselves rather than going all-in on a framework.

## 2. What a control plane has to do

The six control-plane tests below come from a 2026 ADE roundup. The author sells one of the tools (Nimbalyst, which has a paid Teams SKU — disqualified). The *tests* still hold; their product ranking does not.

| Capability | Meaning | ADash now | Gap |
| --- | --- | --- | --- |
| **Assignment** | Point at a *task*, not a chat box. Work outlives the session. | AM/ADash session rows + JJ tasks | Tasks and sessions still two worlds |
| **Isolation** | Worktree / clone / container per agent | JJ worktree arena is spec-only | No worktree column on the fleet board |
| **Glanceable status** | Running / needs you / done / failed without opening a transcript | Attention sort + states | “Needs you” is split across review/blocked; no live agent heartbeat |
| **Review before merge** | Diff, evidence, accept/reject | JJ events + AM review state | No diff viewer; no per-file accept |
| **Engine choice** | Claude, Codex, Grok, OpenCode behind one board | AM `Command` field | Board does not launch or show which CLI is live |
| **Recovery** | Resume after the laptop closes | SQLite hub + AM events | No session attach from the web board |

The most useful product question in that guide: **is the unit of work a session or a task?** Session-centric tools leave you a transcript list. Task-centric tools keep plan, branch, diff, and status after the chat dies. ADash rows are task-shaped (id, state, task, note) but the JJ deck is still closer to a kernel monitor than a control plane.

## 3. Coding-agent boards (steal from these)

Star counts from [sifted-awesome-ai-agents Agent Orchestration ranking](https://github.com/sifted-network/sifted-awesome-ai-agents/blob/main/top100/Agent%20Orchestration.md), captured 2026-08-31.

### Orca ADE — [stablyai/orca](https://github.com/stablyai/orca) (~57.6k)

MIT desktop ADE. Claude Code, Codex, OpenCode, Grok, “any CLI,” each in a git worktree. Desktop + iOS/Android + VPS. Experimental **Agent Dashboard** is a kanban ([docs](https://www.onorca.dev/docs/model/agents-sessions)):

- **Needs You** — permission or question
- **Working**
- **Done** — finished, still reviewable
- **Idle** — quiet ~30 min, **hidden by default**

Cards show last message or task summary, elapsed time, PR/MR status filters. Dispatch is first-class. Design Mode clicks a live UI element into the agent prompt.

**Steal:** Needs-You as the *first* column. Hide idle by default (Grok already folds idle to 8 freshest). Elapsed-time on working rows. Worktree identity on the card. Mobile is optional later, not now.

**Reject:** Computer-use and “25+ agents” surface area. Chat-adjacent tiled IDE as ADash’s home. We are a hub, not an ADE.

### Emdash — [generalaction/emdash](https://github.com/generalaction/emdash) (~5.6k, YC W26)

Apache-2.0, local-first, auto-detects installed CLIs, worktree + branch per task, compare parallel attempts then merge. Tracker ingest: Linear, GitHub, Jira.

**Steal:** Auto-detect which CLIs exist on this PC. Parallel-attempt compare (JJ arena spec already says this). Tracker as assignment source, not as the board itself.

**Reject:** Becoming a desktop Electron app. ADash stays a local FastAPI board.

### Nimbalyst — out

MIT desktop exists, but Teams is a paid SKU for the collaboration layer. Disqualified under the no-paid-feature-gate rule. Taxonomy in their article is still usable; the product is not a dependency.

### Claude Squad / dmux (OSS)

Claude Squad: tmux + worktrees, AGPL-3.0. dmux: worktree multiplexer.

**Steal:** Keyboard-first and terminal-native as a *mode*, not the only UI. JJ command bar already points this way.

**Reject as ADash code:** AGPL copyleft if we vend Squad. Read it; do not merge it. Conductor (proprietary, macOS) is out entirely.

### Grok Agent Dashboard (this pager)

Documented in `~/.grok/docs/user-guide/23-dashboard.md`. Sort: Needs input → Working → Idle → Inactive → Completed → Failed. Dispatch bar on the same screen. Subagents stay under the parent. Idle folding. Pin / stop / peek.

**Steal:** This *is* the live-session layer ADash should deep-link, not rebuild. ADash = projects + JJ kernel; Grok/Claude/Codex dashboards = in-flight agents.

### OpenHands (formerly OpenDevin)

Event stream: agent reasons → emits action → environment executes → observation. Four states per loop. Used as the autonomous-coding reference in O’Reilly’s 2026 toolkit note.

**Steal for JJ:** Make the live run stream an action/observation log, not a chat. ADash already has `events` with types.

## 4. AI OS / personal-agent dashboards

These are closer to JJ than to ADash’s fleet table.

| Product | Shape | Steal | Reject |
| --- | --- | --- | --- |
| **JJ cockpit** (ours) | Command center over kernel DB: tasks, runs, inbox, memory, skills, passports | Already the JJ deck on ADash | Chat-first rewrite |
| **OpenClaw Mission Control** ([openclaw-mission-control](https://github.com/abhi1693/openclaw-mission-control) ~4.1k; vendor writeup [openclawhq.io](https://openclawhq.io/blog/openclaw-mission-control)) | Grid of agents, channel, uptime, skills; start/pause/restart on the card; drag-drop workflows | Card actions (start/pause). Channel/uptime if we ever track OpenClaw | Visual workflow builder, no-code canvas |
| **OpenHuman** (~39k) | Local-first life memory + fleet orchestrator | Local-first memory as *reviewed* court, which JJ already is | Life-log vacuum into the fleet board |
| **ClawX / edict / TinyAGI** | Desktop GUI over OpenClaw; “nine agents + audit”; one-person-company teams | Audit trail as first-class | Office-simulator chrome, 186-agent catalogs |
| **AutoGen Studio** | No-code multi-agent canvas. AutoGen itself is in maintenance; Microsoft Agent Framework is the successor (GA Apr 2026 per Dataiku roundup) | HITL interrupt | Canvas-as-architecture |
| **CrewAI OSS vs Enterprise** | OSS crew framework is separate from paid Enterprise tracing/RBAC | Audit + cost as *events* we already write | Paid enterprise board; role-play crews as the ADash metaphor |

**LangChain Agent Inbox** ([langchain-ai/agent-inbox](https://github.com/langchain-ai/agent-inbox)): dedicated UX for human-in-the-loop interrupts from LangGraph. The whole product is an inbox. That is the strongest single-screen analogue to JJ’s approval panel and ADash `blocked`/`review`.

## 5. Observability boards (do not become these)

LangSmith is **closed SaaS** — out as a product. Langfuse self-host MIT covers tracing, evals, annotation, playground; `/ee` (SCIM, extra audit, retention) is commercial and we will not use it. Arize Phoenix OSS exists; Helicone has a cloud SKU — prefer Phoenix/Langfuse self-host or just ADash events.

**Steal (from public OSS / docs, implement in ADash):** Thread = session id. Collapsed “same tool 3×” in a run stream. Cost as an event field (JJ NEXT_PHASES “Cost & Trace Board”). Annotation queue = review state.

**Reject:** LangSmith Cloud. Langfuse Cloud. Latency charts as the home screen. Drag-and-drop widget builders. “Insights” tiles with no action (forbidden by `DESIGN_TASTE.md`). Paying for audit logs we can append to SQLite ourselves.

## 6. Design patterns that survive contact with JJ taste

`C:\ALLU\projects\Jarvis\DESIGN_TASTE.md` already bans ChatGPT wrappers, no-code boards, Notion clones, pastel gradients, cards with no action, sparkle icons.

Patterns that agree with that file *and* with the 2026 control-plane products:

1. **Attention, not alphabet.** Orca Needs-You first. Grok Needs-input first. ADash attention scores already do this for 226 projects. Keep it. Kanban columns help *sessions*; they drown *projects*.
2. **Command bar as steering wheel.** JJ COMMAND_DECK, Grok dispatch, Claude Squad. Typed verbs that hit the same stores as the CLI (12-factor: own control flow; tools are structured outputs).
3. **Inbox is a place, not a badge.** Agent Inbox, HumanLayer factor 7 (contact humans with tool calls). Review + blocked + JJ approvals should be one “needs Joshua” surface.
4. **Live stream is actions, not chat.** OpenHands event loop. Cards: who, what tool, evidence, Approve/Abort.
5. **Worktree / lane as identity.** Every parallel coding-agent product converged here. JJ WORKTREE_ARENA.md is the spec; ADash should show lane + branch when present.
6. **Idle is noise.** Grok folds it. Orca hides it. Do not paginate 200 idle AM sessions as the home view.
7. **One engine picker, your keys.** Orca and Emdash refuse to resell inference (MIT / Apache-2.0). ADash must not become a proxy bill.
8. **Dense, keyboard, split panes.** Bloomberg / CIC / war-room, which DESIGN_TASTE already named. Not empty heroes.

Patterns to refuse even though they poll well on GitHub:

- Glassmorphism + micro-animations (multi-agent-orchestrator marketing).
- Visual DAG editors as the *daily* UI (FastGPT, Bisheng, CrewAI studio). Fine as a rare debug view (Langfuse expanded graph).
- ROI / “board-ready investment” widgets.
- Swarm dashboards that spawn unsupervised subordinates. Review becomes the bottleneck (duplicated fixes, dropped work).
- Session lists without durable task state.

## 7. Recommended ADash information architecture

Three layers, three URLs, one SQLite spine. Do not merge them into one “AI OS.”

```
/                         fleet board     (projects × PC, attention-sorted)
/inbox                    needs Joshua    (review + blocked + JJ approvals + Grok needs-input)
/project/{pc}/{id}        generic dossier or custom deck
/project/pc1/jarvis       JJ command deck (kernel, already shipped)
```

Later, if earned:

```
/sessions                 live CLIs      (deep-link Grok/Claude/Codex; do not scrape transcripts into SQLite)
/lanes                    worktrees      (JJ arena + git probe cache, never git-in-request)
```

Per-project custom decks stay a `config/fleet.json` map (`project_dashboards`). Jarvis is the prototype. Next candidates are projects that already have a kernel or a cockpit (OpenClaw profile, BarMatrix/MEV if it has an ops surface) — not every one of the 226 rows.

### Fleet board columns that actually help

Keep: attention, state, pc, id, title, path, task, updated.

Add when cheap and true:

- **engine** (claude / codex / grok / python) from AM `Command`
- **needs-you** boolean (review, blocked, or JJ inbox > 0)
- **deck** badge (already on jarvis)
- **open JJ/AM tasks count** for kernel projects

Do not add: sparkline, health pie, token burn, “AI score.”

### JJ deck next (aligned with COMMAND_DECK.md, not with Orca)

Already: next-work, inbox, ledger, runs, memory, passports, command bar.

Highest-leverage steals that match open JJ tasks:

| JJ task | Control-plane pattern |
| --- | --- |
| C9 send-to-Codex | Orca/Emdash dispatch on the task card |
| C12 abort lane | Grok Ctrl+X stop; Orca Needs-You |
| C1 verb grammar | Command bar = CLI |
| P7 `jj next` | One Next task, not a wall of open |
| P23 / P26 brief | Assignment pack on dispatch |
| Cost board | LangSmith cost as event field, not a chart home |

## 8. What not to adopt as ADash

- LangGraph / CrewAI / Microsoft Agent Framework as the *dashboard*. They are runtimes. JJ already is the runtime.
- Replacing ADash with Orca/Emdash. Those are ADEs for one repo’s parallel agents. ADash is the cross-project, cross-PC hub.
- Chat as the shell. DESIGN_TASTE and 12-factor both say structured tools + owned control flow.
- Syncing live SQLite across PCs (CONTROL_CENTER.md). Dashboards read the hub; satellites push events.
- Building 226 custom decks. Plugin map + generic dossier. Custom only when a project has a kernel.

## 9. Sources

- Licence filter: OSI-open / fully free self-host only. No paid SKU for inbox, fleet, traces, or worktrees.
- [Nimbalyst, Best AI Agent Orchestration Platforms 2026](https://nimbalyst.com/blog/best-ai-agent-orchestration-platforms-2026/) — taxonomy + six control-plane tests. Vendor-authored and has a paid Teams SKU; claims about Nimbalyst itself discounted; product disqualified.
- [sifted-awesome-ai-agents / Agent Orchestration.md](https://github.com/sifted-network/sifted-awesome-ai-agents/blob/main/top100/Agent%20Orchestration.md) — star ranking 2026-08-31.
- [stablyai/orca](https://github.com/stablyai/orca) and [Orca agent dashboard docs](https://www.onorca.dev/docs/model/agents-sessions).
- [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents).
- [langchain-ai/agent-inbox](https://github.com/langchain-ai/agent-inbox).
- [LangSmith dashboards](https://docs.langchain.com/langsmith/dashboards), [view traces](https://docs.langchain.com/langsmith/view-traces).
- [Langfuse July 2026 update](https://langfuse.com/blog/2026-07-31-langfuse-july-update).
- [O’Reilly, The Open Source Agent Toolkit in 2026](https://www.oreilly.com/radar/the-open-source-agent-toolkit-in-2026/).
- [AgenticsPulse, CrewAI vs AG2 vs LangGraph vs OpenAI Agents SDK](https://agenticspulse.com/posts/crewai-vs-autogen-vs-langgraph-best-framework-2026.html).
- Grok user-guide `23-dashboard.md` (installed build).
- JJ `DESIGN_TASTE.md`, `COMMAND_DECK.md`, `NEXT_PHASES.md` at `C:\ALLU\projects\Jarvis`.
- ADash `CONTROL_CENTER.md`, live board `/` and `/project/pc1/jarvis`.
