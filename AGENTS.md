# AGENTS.md

Repository-wide instructions for Codex and other agents working in this repo.

More specific `AGENTS.md` files in subdirectories take precedence over this file for work in those paths.

## Project Overview

**AgentinaBox** is a Dockerized AI code review sidecar.

It receives code and context via MCP tool calls, sends that bundle to an inner model reviewer, and returns structured findings. The primary reviewer backend is the GitHub Copilot SDK, with fallback backends planned separately.

The project is currently in **spec / planning / workflow design** mode. Most important work lives in:

- `specs/` for product and technical specs
- `agent-loop/` for the builder / judge coordination workflow

## Current Architecture Direction

The intended MVP architecture is:

- **MCP server** exposing `start_review`, `discuss`, `get_review_summary`, `list_sessions`
- **Inner review backend**: GitHub Copilot SDK first
- **Web dashboard** on `localhost:8080`
- **Single Docker container**
- **No direct host-repo filesystem access from inside the review container**

## Non-Negotiable Principles

These principles apply unless Peter explicitly decides otherwise:

1. **Project-agnostic reviewer**
   The review server must not rely on hardcoded repo-specific knowledge. Context must arrive through MCP inputs.

2. **No host repo volume mounts into the review container**
   The review container should not browse the host repository directly.

3. **Security boundary matters**
   The system must denylist obvious secret-bearing files and avoid sending sensitive files to third-party review backends.

4. **Model-agnostic external interface**
   The MCP interface should stay stable even if the inner review backend changes.

5. **Simplicity first**
   Prefer the simplest architecture that satisfies the current phase. Avoid premature complexity.

## Working Style in This Repo

- Specs are the source of truth for intended behavior.
- When evaluating design or implementation, prefer consistency with the numbered specs over ad hoc invention.
- If working on a feature area with a numbered spec, read that spec first.
- If the task changes scope or contradicts an accepted spec, escalate to Peter instead of silently redefining it.

## Specs

Important conventions:

- Specs live under `specs/NNN-feature-name/spec.md`
- New major capabilities should generally be represented by a numbered spec
- If reviewing a spec, prioritize:
  - contradictions
  - missing behavior on important edge cases
  - hidden workflow assumptions
  - risks that would cause implementation churn later

## Agent Loop

The **canonical builder / judge workflow** is now in:

- `agent-loop/PROTOCOL.md`

If you are working on anything under `agent-loop/`, you MUST also read:

- this file (root `AGENTS.md`)
- `agent-loop/PROTOCOL.md`
- `agent-loop/ANTIPATTERNS.md`

Treat `agent-loop/PROTOCOL.md` as the canonical coordination document for multi-agent work. Older discussion documents under `specs/` may exist, but the protocol in `agent-loop/` is the live one.

### Builder / Judge Roles

Within the `agent-loop/` workflow:

- **Claude Code** is the builder
- **Codex** is the judge
- **Peter** is the coordinator and final decision-maker

Codex must not drift into being the primary builder when acting as judge.

### File Ownership in Agent Loop

When operating inside `agent-loop/`:

- Do not edit `builder.md` if you are acting as judge
- Do not edit `judge.md` if you are acting as builder
- Preserve round history — rounds may only be moved to archive files via the Context Management process, never deleted or modified in place
- Update `status.json` when the protocol requires it

### Quick Reference

**Builder (Claude Code):**
1. Read `task.md` for goal, scope, acceptance criteria
2. Read `judge.md` if it exists (previous round feedback)
3. Read **Phase Summaries** from both archive files (if they exist)
4. Perform context management checks (see PROTOCOL.md Context Management):
   - Phase compaction: if active file contains rounds from a prior phase, compact first
   - Round archival: if active file has 2+ rounds and you're writing round N >= 3, archive oldest
5. Append a new `## Round N — [phase]` section to `builder.md`
6. Update `status.json`: state → `ready_for_judge`
7. Do NOT edit `judge.md` or `judge-archive.md`

**Judge (Codex):**
1. Read `task.md` for goal, scope, acceptance criteria
2. Read `builder.md` (latest round)
3. Review any changed artifacts referenced by the builder
4. Read **Phase Summaries** from both archive files (if they exist)
5. Perform context management checks (see PROTOCOL.md Context Management):
   - Phase compaction: if active file contains rounds from a prior phase, compact first
   - Round archival: if active file has 2+ rounds and you're writing round N >= 3, archive oldest
6. Append a new `## Round N — [phase]` section to `judge.md` with verdict and findings
7. Update `status.json`: state → verdict value
8. Do NOT edit `builder.md` or `builder-archive.md`

### Boundaries

**Always do:** Read `task.md` first. Read Phase Summaries from archive files (if they exist). Use structured output from PROTOCOL.md. Use stable finding IDs (B-1, H-1, M-1, L-1). Perform context management checks before writing new rounds. Update `status.json` after writing. Check `agent-loop/ANTIPATTERNS.md` before finalizing each round.

**Ask Peter first:** Changing scope or ACs in `task.md`. Expanding beyond the original spec. Disagreeing for 2+ consecutive rounds on the same point.

**Never do:** Edit the other agent's artifact or archive. Skip reading `task.md`. Delete or modify rounds in place (archival via Context Management is the only permitted move). Make product/scope decisions.

## Implementation Preferences

Unless a spec says otherwise, prefer:

- Python 3.11+
- FastAPI + uvicorn
- Jinja2 server-rendered UI
- Simple persistence choices first
- Native HTML where possible instead of unnecessary frontend complexity

Avoid unnecessary additions such as:

- React for simple dashboard pages
- WebSockets if SSE or refresh is enough
- PostgreSQL when simpler storage is sufficient for the current scope

## Review Expectations

When acting as reviewer or judge:

- Findings should be concrete and actionable
- Call out blockers and high-risk issues first
- Prefer evidence over assertion
- If no issues are found, say so explicitly

When acting on specs, prioritize product and workflow correctness over polish.

When acting on code, prioritize:

- correctness
- safety
- test adequacy
- behavioral regressions
- mismatch with specs

## Escalate to Peter When

- a scope decision is required
- specs conflict materially
- a requested change would expand the task
- the correct path depends on missing product context
- builder and judge have repeated unresolved disagreement

## Practical Rule

If a task is part of the builder / judge loop, follow the `agent-loop/` protocol.

If a task is normal repo work outside that loop, use this file plus the relevant specs as your main instructions.
