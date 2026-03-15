# Peter's Cheatsheet

This project uses two AI agents working on shared files. You don't relay context — you just trigger each step.

## The Setup

| Agent | Role | Tool |
|-------|------|------|
| Claude Code | Builder — designs, codes, tests | Claude Code CLI |
| Codex | Judge — reviews, finds issues, gives verdicts | Codex CLI |
| You | Coordinator — decides scope, tradeoffs, when to stop | Both terminals |

## Day-to-Day Commands

### Start a new feature
```
Claude:  /loop.build new <one-line description>
```
This creates the task folder, writes the spec (using speckit templates), and marks it ready for review.

### Send it to the judge
```
Codex:   judge <task-id>
```
Example: `judge 001-ai-code-reviewer`

### Check the verdict
Open `agent-loop/<task-id>/judge.md` and look at the latest round:
- **accepted** → move to next phase
- **needs_revision** → send back to Claude
- **escalated** → you need to make a decision

### Send it back to the builder (after needs_revision)
```
Claude:  /loop.build <task-id>
```
Or just `/loop.build` — it auto-detects the active task.

### Advance to the next phase (after accepted)
```
Claude:  /loop.build <task-id> <phase>
```
Phases in order: `specify` → `design` → `plan` → `build` → `test` → `release`

### Check status anytime
```
Claude:  /loop.status
```

## The Phases (with Speckit Integration)

`/loop.build` runs the right speckit process for each phase automatically. You don't need to call `/speckit.*` commands separately.

| Phase | What Claude does (speckit inside) | What Codex checks |
|-------|----------------------------------|------------------|
| specify | Writes `spec.md` + quality checklist (= `/speckit.specify`) | Completeness, testability, consistency |
| design | Research + data model + contracts + plan.md (= `/speckit.plan`) | Feasibility, constitution compliance, risks |
| plan | Generates dependency-ordered `tasks.md` (= `/speckit.tasks`) | Step size, coverage, dependencies |
| build | Implements per tasks.md with TDD (= `/speckit.implement`) | Correctness, spec match, test quality |
| test | Full test suite + coverage analysis | Coverage, edge cases, residual risk |
| release | Final summary, all ACs checked | Readiness, no regressions |

### Speckit artifacts produced per phase

| Phase | Files created/updated |
|-------|----------------------|
| specify | `specs/NNN-name/spec.md`, `specs/NNN-name/checklists/requirements.md` |
| design | `{feature-dir}/research.md`, `data-model.md`, `contracts/`, `plan.md` |
| plan | `{feature-dir}/tasks.md` |
| build | Source code + tests (per tasks.md) |
| test | Test results, coverage report |
| release | Final AC checklist in builder.md |

## When You Get Pulled In

You only need to act when:
- **escalated** — the agents disagree or need a product decision
- **Phase transition** — you say `/loop.build <id> <next-phase>` to advance
- **Scope change** — you edit `task.md` directly
- **Done** — you decide to merge, PR, or stop

## Quick Decision Guide

```
Verdict says "escalated"?
  → Read the "Open Questions" in judge.md
  → Decide and tell Claude what to do

Verdict says "needs_revision"?
  → Just type: /loop.build <task-id>
  → Claude reads the findings and fixes them

Verdict says "accepted"?
  → Type: /loop.build <task-id> <next-phase>
  → Or if it was the release phase, you're done
```

## Key Files

| File | What it is | Who owns it |
|------|-----------|-------------|
| `agent-loop/<task>/task.md` | Goal, scope, acceptance criteria | You |
| `agent-loop/<task>/builder.md` | Claude's proposals and responses | Claude |
| `agent-loop/<task>/judge.md` | Codex's verdicts and findings | Codex |
| `agent-loop/<task>/status.json` | Machine-readable state | Both agents update it |
| `agent-loop/PROTOCOL.md` | The full protocol rules | Reference doc |
| `agent-loop/ANTIPATTERNS.md` | Known mistakes catalog — agents check each round | Both agents maintain it |
| `AGENTS.md` | Instructions both agents read | Reference doc |
| `CODEX.md` | Codex-specific judge workflow | Reference doc |
| `CLAUDE.md` | Claude-specific builder context | Reference doc |

## You DON'T Need To

- Call `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`, or `/speckit.implement` separately — `/loop.build` handles all of that
- Relay context between agents — everything is in the shared files
- Explain what round you're on — the agents read `status.json`
- Summarize judge findings for Claude — Claude reads `judge.md` directly

## Rules You Set

- **Lightweight mode** (skip the full loop for trivial changes): you decide when it's allowed
- **Max 5 rounds** per phase before auto-escalation to you
- **Conventional commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- **Constitution** at `.specify/memory/constitution.md` — the non-negotiable principles

## Example: Full Feature Lifecycle

```
/loop.build new MCP review server with Copilot SDK     ← creates task, writes spec
  codex: judge 001-ai-code-reviewer              ← reviews spec
/loop.build 001-ai-code-reviewer                      ← addresses feedback
  codex: judge 001-ai-code-reviewer              ← accepted

/loop.build 001-ai-code-reviewer design               ← research + data model + contracts
  codex: judge 001-ai-code-reviewer              ← accepted

/loop.build 001-ai-code-reviewer plan                 ← generates tasks.md
  codex: judge 001-ai-code-reviewer              ← accepted

/loop.build 001-ai-code-reviewer build                ← implements with TDD
  codex: judge 001-ai-code-reviewer              ← needs_revision (H-1: missing test)
/loop.build 001-ai-code-reviewer                      ← fixes it
  codex: judge 001-ai-code-reviewer              ← accepted

/loop.build 001-ai-code-reviewer test                 ← full test suite + coverage
  codex: judge 001-ai-code-reviewer              ← accepted

/loop.build 001-ai-code-reviewer release              ← final readiness check
  codex: judge 001-ai-code-reviewer              ← accepted ✓

→ merge / PR / ship
```
