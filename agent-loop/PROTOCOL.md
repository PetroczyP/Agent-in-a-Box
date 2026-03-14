# Builder / Judge Protocol (Dual-Agent Collaboration Loop)

**Version**: 1.1.0
**Ratified**: 2026-03-14 (v1.1: added Context Management — phase compaction + round archival)

This protocol governs collaboration between Claude Code (builder) and Codex (judge) on the AgentinaBox project. Peter is the decision-maker and coordinator.

## Roles

| Role | Agent | Owns |
|------|-------|------|
| **Builder** | Claude Code | Design proposals, spec changes, implementation, tests, test execution, evidence |
| **Judge** | Codex | Review findings, correctness analysis, consistency checks, quality-gate verdicts, escalation |
| **Coordinator** | Peter | Product direction, tradeoff decisions, scope, arbitration, lightweight-mode approval |

The builder produces. The judge evaluates. Neither edits the other's artifact.

## Industry Basis

This protocol is based on the **generator/critic pattern** documented in Google's Agent Development Kit and validated across multi-agent coding workflows. Key research findings incorporated:

- The judge must be at least as capable as the builder to produce reliable evaluations
- Hard-coded evaluation criteria (our structured templates) outperform open-ended review prompts
- File-based coordination (AGENTS.md pattern, 60k+ repos) is the proven approach when agents don't share a direct channel
- A max-rounds cap prevents infinite iteration loops
- Append-only round history is essential for auditability

## Folder Structure

```
agent-loop/
  PROTOCOL.md          # this file
  ANTIPATTERNS.md      # known anti-patterns — both agents check before each round
  NNN-task-name/
    task.md            # owned by Peter (seeded by builder)
    builder.md         # owned by Claude — current phase, recent rounds only
    judge.md           # owned by Codex — current phase, recent rounds only
    builder-archive.md # owned by Claude — phase summaries + archived rounds
    judge-archive.md   # owned by Codex — phase summaries + archived rounds
    status.json        # coordination state
```

## File Ownership Rules

- Claude MUST NOT edit `judge.md` or `judge-archive.md`
- Codex MUST NOT edit `builder.md` or `builder-archive.md`
- Claude MAY respond to judge findings in a new round section of `builder.md`
- Codex MAY review that update in a new round section of `judge.md`
- Peter MAY edit any file

## Round History

Both `builder.md` and `judge.md` contain **only the current phase's recent rounds**. Older content lives in the corresponding archive file (`builder-archive.md`, `judge-archive.md`).

Within a phase, each round is a new section:

```markdown
## Round 1 — design
...content...

## Round 2 — design
...content...
```

Rounds in the active file MUST NOT be modified once written, except by the archival process described in Context Management below.

## Context Management

Active files (`builder.md`, `judge.md`) are kept small through two mechanisms: phase compaction and within-phase round archival. Raw content is preserved in archive files for auditability.

### Phase Compaction

**Trigger (deterministic, from repo state):** Before writing a round, read your active file and find the first `## Round N — [phase]` header. Compare `[phase]` to the current phase in `status.json`. If they differ, compaction is needed. If no round headers exist (empty or back-reference only), no compaction is needed.

Since the builder writes first in every phase, the builder compacts first. The judge compacts when writing their first review in the new phase.

When compaction is needed, each agent MUST:

1. Write a **phase summary** to their archive file (`builder-archive.md` or `judge-archive.md`)
2. Move the raw round content from the active file to the archive file (below the summary)
3. Clear the active file, leaving only a back-reference line

**Phase summary template** (builder):

```markdown
## [design] Phase Summary (rounds 1-5, accepted)

### Key Decisions
- D-1: Short description of decision
- D-2: ...

### Findings Resolved
- H-1: Short description → resolution
- M-1: ...

### Artifacts Produced
- path/to/artifact.md — what it contains

### Deferred / Out of Scope
- Item deferred to spec NNN
(or "None")
```

**Phase summary template** (judge):

```markdown
## [design] Phase Summary (rounds 1-5, accepted)

### Key Findings
- H-1: Short description → resolved in round N
- M-1: ...

### Escalations
- Round 4: escalated [topic] → Peter resolved by [decision]
(or "None")

### Acceptance Criteria Status
- AC-1: pass
- AC-2: pass
- ...

### Verification Notes
- Key verifications that informed the phase outcome
```

**Back-reference line** (placed at the top of the cleared active file):

```markdown
<!-- Phase history: design (5 rounds, accepted), plan (4 rounds, accepted) — see [builder|judge]-archive.md -->
```

### Within-Phase Round Archival

**Trigger (deterministic, from repo state):** Before writing a round, count the `## Round` headers in your active file. If there are 2 or more, and you are about to write Round N where N >= 3, archive the oldest rounds.

When archival is triggered, each agent MUST:

1. Move rounds 1 through N-2 from their active file to their archive file under a clearly labeled section
2. Leave the back-reference line and rounds N-1 onward in the active file

This ensures the active file contains at most 2 complete rounds plus the current work.

**Archive section header for moved rounds:**

```markdown
## [design] Archived Rounds

### Round 1 — design (builder)
[original round content]

### Round 2 — design (builder)
[original round content]
```

### Archive File Layout

Archive files MUST follow this layout — summaries at the top, raw rounds at the bottom:

```markdown
# Builder Archive — 001-ai-code-reviewer

## Phase Summaries
<!-- Agents read this section every round -->

### [design] Phase Summary (rounds 1-5, accepted)
...summary content...

### [plan] Phase Summary (rounds 1-4, accepted)
...summary content...

---

## Raw Archived Rounds
<!-- Agents read this section only when tracing specific findings or decisions -->

### [design] Round 1 — builder
[original content]

### [design] Round 2 — builder
[original content]

...
```

The `## Phase Summaries` section is always read. The `## Raw Archived Rounds` section is read only on demand.

Archive files are created on first use — when the first archival occurs. They do not need to exist before that.

### Reading Archived Content

- Agents MUST read the **Phase Summaries** section of both archive files **every round** (summaries are ~15 lines per completed phase — this is cheap and prevents stateless agents from missing prior-phase decisions)
- Agents MAY read the **Raw Archived Rounds** section when they need to trace a specific finding ID or decision to its original context
- Within a phase, the active files always contain the finding/response pair for the two most recent rounds — the archives are for cross-phase context, not within-phase work

### What Must Be Preserved in Phase Summaries

Phase summaries MUST include:
- All decisions that constrain future phases (e.g., "in-memory storage, not SQLite")
- All finding IDs and their resolutions (so future rounds can reference them)
- All artifacts produced or modified
- Items explicitly deferred to future specs

Phase summaries MUST NOT include:
- Full round content (that goes in the raw archive section)
- Inline code blocks or test output (reference the file instead)
- Discussion that led to a decision (only the decision itself)

## status.json

```json
{
  "task_id": "001-core-review-server",
  "phase": "design",
  "state": "ready_for_builder",
  "round": 1,
  "max_rounds": 5,
  "builder": "claude",
  "judge": "codex",
  "verdict": null,
  "updated_at": "2026-03-13T21:00:00Z",
  "history": [
    { "round": 1, "phase": "specify", "actor": "builder", "verdict": null, "timestamp": "..." },
    { "round": 1, "phase": "specify", "actor": "judge", "verdict": "needs_revision", "timestamp": "..." }
  ]
}
```

### State transitions

| From | To | Triggered by |
|------|----|-------------|
| `ready_for_builder` | `ready_for_judge` | Builder writes/updates `builder.md`, updates `status.json` |
| `ready_for_judge` | `needs_revision` | Judge writes `judge.md` with `needs_revision` verdict |
| `ready_for_judge` | `accepted` | Judge writes `judge.md` with `accepted` verdict |
| `ready_for_judge` | `escalated` | Judge writes `judge.md` with `escalated` verdict |
| `needs_revision` | `ready_for_judge` | Builder addresses findings, updates `builder.md` |
| `escalated` | any | Peter decides and updates `status.json` |

## Standard Loop

1. Peter defines or approves `task.md`
2. Builder reads `task.md`, performs context management checks (phase compaction if active file contains prior-phase rounds, round archival if active file has 2+ rounds and N >= 3), writes `builder.md` (Round N), sets state to `ready_for_judge`
3. Judge reads `task.md` + `builder.md` + Phase Summaries from archive files, writes `judge.md` (Round N) with verdict
4. If `needs_revision`: builder reads findings, performs context management checks, appends new round to `builder.md`, sets `ready_for_judge`
5. If `accepted`: done. Peter decides to merge/continue
6. If `escalated`: Peter resolves the issue
7. If `max_rounds` reached without acceptance: auto-escalate to Peter

## Phases

Phases progress in order: `specify` → `design` → `plan` → `build` → `test` → `release`

When a phase reaches `accepted`, the coordinator advances to the next phase.

| Phase | What the builder produces | What the judge checks | Mode |
|-------|-------------------------|----------------------|------|
| specify | Feature spec (user scenarios, requirements, ACs) | Completeness, testability, consistency | Full loop |
| design | Technical design (modules, interfaces, data models) | Feasibility, constitution compliance, risks | Full loop |
| plan | Ordered implementation steps with dependencies | Step granularity, coverage of requirements, TDD fit | Full loop |
| build | Code + tests (TDD) | Correctness, spec compliance, test quality | Full for major features |
| test | Full test results, coverage analysis | Coverage gaps, edge cases, residual risks | Light (1-2 rounds) |
| release | Final summary, all ACs checked | Readiness, no regressions, known limitations documented | Full, single round |

## Lightweight Mode

For low-risk tasks (docs updates, isolated test additions, small bug fixes that don't change public interfaces):

- Peter decides whether lightweight mode is allowed
- Skip `status.json` — just `builder.md` and `judge.md`
- Single round expected
- NOT allowed for: spec changes, architectural changes, workflow changes, cross-file behavioral changes

## Builder Output Format

```markdown
## Round N

### Summary
- ...

### Changes Since Last Round
- ... (skip for round 1)

### Design / Implementation Notes
- ...

### Test Evidence
- ...

### Responses to Judge Findings
- H-1: addressed by ...
- M-2: declined because ...
(skip for round 1)

### Verification
- Checked: [what was web-searched or self-verified]
- Corrections: [what changed as a result, or "None"]

### Remaining Risks
- ...
```

Rules:
- Respond explicitly to every judge finding using the judge's finding IDs
- If declining a suggestion, state the reason plainly
- Include evidence (spec references, test output, before/after examples)
- Make it easy for the judge to review deltas, not re-read the whole project
- Run CoVe self-check and web research before marking ready for judge

## Judge Output Format

```markdown
## Round N

### Verdict
accepted | needs_revision | escalated

### Blockers
- B-1: ...

### High
- H-1: ...
- H-2: ...

### Medium
- M-1: ...

### Low
- L-1: ...

### Acceptance Check
- AC-1: pass | fail | untested
- AC-2: pass | fail | untested

### Verification
- Checked: [what was web-searched or self-verified]
- Corrections: [what changed as a result, or "None"]

### Open Questions
- ...
```

Rules:
- Use stable finding IDs (B-1, H-1, M-1, L-1) so the builder can reference them
- Findings must be concrete and actionable, not generic commentary
- If there are no findings in a severity level, say "None"
- `accepted` only if zero blockers and zero unresolved high-severity issues
- `needs_revision` if blockers or highs remain
- `escalated` if the issue is about scope, intent, or product tradeoffs

## Escalation Rules

Escalate to Peter when:
- Builder and judge disagree for 2 consecutive rounds on the same finding
- A product decision is required that neither agent can make
- The spec is ambiguous and the ambiguity affects the verdict
- A fix would expand scope materially
- The judge's finding depends on information neither agent has (user research, business constraint)
- The builder cannot satisfy a requirement without changing the task definition

## Verification Requirements

Both agents have knowledge cutoffs and can hallucinate API details, SDK behavior, or library features. To mitigate this:

### Chain of Verification (CoVe)

After producing an artifact, each agent MUST self-verify before finalizing:

1. **Generate**: Produce the artifact (spec, design, code, review)
2. **Question**: Generate 3-5 verification questions about your own output — focus on factual claims, API usage, library behavior, and assumptions that could be wrong due to knowledge cutoff
3. **Verify**: Answer each question independently. Use web search for any claim about external tools, SDKs, APIs, or libraries. Flag conflicts between your initial output and verification answers.
4. **Revise**: Fix any inconsistencies found. Document what was corrected in the artifact.

### Web Research Cross-Check

Both agents MUST use web search to validate claims in these situations:

| Situation | What to verify |
|-----------|---------------|
| Referencing an SDK or API | Current version, correct method names, parameter signatures |
| Citing documentation | URL still exists, content matches what you claim |
| Stating a tool's capability or limitation | Check current docs, not training data |
| Using a library pattern | Verify against current examples/changelog |
| Making a compatibility claim | Check current release notes |

**When to search:**
- **Builder**: During `specify` (validate product assumptions), `design` (validate tech choices, SDK APIs), `build` (validate library usage before coding)
- **Judge**: When a finding depends on external tool behavior, or when the builder's claims about an API/SDK seem uncertain

**Where to record**: Each agent includes a `### Verification` section in their round output listing what was checked and any corrections made.

### Why This Matters

The Copilot SDK research document required 3 rounds of cross-validation with 25+ corrections (wrong package names, retired models, incorrect API patterns, stale auth methods). This is the norm, not the exception, for any work involving external tools.

## Norms

1. **Builder builds, judge judges** — Claude doesn't wait for Codex to design. Codex doesn't implement.
2. **Review the artifact, not the agent** — Strict on quality, calm in tone.
3. **Keep rounds incremental** — Small, well-explained changes. Large rewrites are expensive to review.
4. **Evidence over assertions** — Claims require proof (test output, spec references, examples).
5. **Product decisions are Peter's** — Codex flags tradeoffs. Peter decides.
6. **Verify before you assert** — Use CoVe self-check and web research for any claim about external tools, APIs, or libraries. Knowledge cutoff errors are expected, not exceptional.
7. **Learn from mistakes** — Both agents MUST check `agent-loop/ANTIPATTERNS.md` before finalizing each round. After receiving feedback, check if the findings reveal a new anti-pattern worth cataloging. The judge SHOULD cite AP-IDs in findings when a known anti-pattern is detected.
