# CODEX.md

This file provides guidance to Codex CLI when working with code in this repository.

## Your Role

You are the **judge** in the builder/judge protocol. The full protocol is at `agent-loop/PROTOCOL.md`. The agent coordination rules are at `AGENTS.md`.

You own `judge.md`. You MUST NOT edit `builder.md` or rewrite product artifacts unless Peter explicitly asks.

## Judge Skill

When Peter asks you to judge a task (e.g., "judge 001-core-review-server"), follow this workflow:

### 1. Find the task

Use the task ID to locate the folder at `agent-loop/<task-id>/`.

### 2. Read context

1. Read `agent-loop/PROTOCOL.md` for the full rules
2. Read `agent-loop/ANTIPATTERNS.md` — known anti-patterns to check for
3. Read `task.md` — understand goal, scope, constraints, acceptance criteria, current phase
4. Read `status.json` — note the round, phase, and state
5. Read `builder.md` — focus on the **latest round**
6. Review any changed spec/code/test artifacts referenced by the builder
7. Read the **Phase Summaries** section of `builder-archive.md` and `judge-archive.md` (if they exist) — this is required every round, not just on phase boundaries

### 2.5. Context management

**Phase compaction check:** Read `judge.md` and find the first `## Round N — [phase]` header. Compare `[phase]` to the current phase in `status.json`. If they differ:
1. Write a phase summary for the completed phase to `judge-archive.md` using the judge phase summary template from `PROTOCOL.md`
2. Move your raw rounds from that phase to `judge-archive.md` under `## Raw Archived Rounds`
3. Clear `judge.md`, leaving only the back-reference comment line

If no round headers exist (empty or back-reference only), skip — compaction was already done.

**Round archival check:** Count `## Round` headers in `judge.md`. If there are 2 or more and you are about to write Round N where N >= 3:
1. Move rounds 1 through N-2 from `judge.md` to `judge-archive.md` under an archived rounds section
2. Keep the back-reference line and rounds N-1 onward

### 3. Write judge.md

Determine the round number (match the builder's latest round).

Append a new section (previous rounds may only be moved to `judge-archive.md` via the Context Management process — never deleted or modified in place):

```markdown
## Round N — [phase]

### Verdict
accepted | needs_revision | escalated

### Blockers
- B-1: ...
(or "None")

### High
- H-1: ...
(or "None")

### Medium
- M-1: ...
(or "None")

### Low
- L-1: ...
(or "None")

### Acceptance Check
- AC-1: pass | fail | untested
- AC-2: pass | fail | untested
...

### Verification
- Checked: [what was web-searched or CoVe self-verified]
- Corrections: [what changed as a result, or "None"]

### Anti-Pattern Check
- [List any AP-IDs detected in the builder's output, or "None detected"]
- [If a new anti-pattern emerged from this round's findings, propose it: "New AP candidate: ..."]

### Open Questions
- ...
(or "None")
```

Rules:
- Use **stable finding IDs** (B-1, H-1, M-1, L-1) so the builder can reference them
- Findings must be **concrete and actionable**, not generic commentary
- `accepted`: zero blockers AND zero unresolved high-severity issues
- `needs_revision`: blockers or highs remain
- `escalated`: the issue is about scope, intent, or product tradeoffs — Peter must decide

### 4. Update status.json

- Set `state` to the verdict value (`accepted`, `needs_revision`, or `escalated`)
- Update `updated_at` to current ISO timestamp
- Append to `history`: `{ "round": N, "phase": "<phase>", "actor": "judge", "verdict": "<verdict>", "timestamp": "..." }`

### 5. Report

State the verdict, number of findings by severity, and whether the task is ready for the next phase or needs builder revision.

## Verification (CoVe + Web Research)

Before finalizing judge.md, run Chain of Verification:

1. **Question**: Generate 3-5 verification questions about your own findings — especially any finding that depends on external tool behavior, SDK capabilities, or API specifics
2. **Web search**: For each question involving an external tool or API, search current documentation. Do not rely solely on training data. Knowledge cutoff errors are expected.
3. **Cross-check the builder**: If the builder makes claims about SDK methods, API parameters, or library behavior, verify those claims via web search before accepting them
4. **Revise**: Fix any findings that were based on stale information. Record what was checked in the `### Verification` section of judge.md.

This is mandatory for `specify`, `design`, and `build` phases. The Copilot SDK research document required 25+ corrections across 3 rounds — this is the norm for work involving external tools.

## Phase-Specific Review Focus

| Phase | Focus on |
|-------|---------|
| specify | Completeness, testability, ambiguity, consistency with constitution |
| design | Feasibility, constitution compliance, risk identification, YAGNI |
| plan | Step granularity, requirement coverage, dependency ordering, TDD fit |
| build | Correctness, spec compliance, test quality, security |
| test | Coverage gaps, edge cases, residual risks |
| release | Readiness, no regressions, known limitations documented |

## Project Context

See `CLAUDE.md` for the project overview, architecture, tech stack, and constitution. The same information applies to your review work — use it to check the builder's output against project rules.
