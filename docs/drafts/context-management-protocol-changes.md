# Context Management Protocol Changes — Draft v2

**Status**: Revised after judge feedback (H-1, H-2, M-1)
**Date**: 2026-03-14
**Addresses**: builder.md / judge.md growing unboundedly (~1000+ lines), causing Codex ordering errors and context window pressure

---

## Problem

After 18 rounds across 4 phases for task 001, both `builder.md` and `judge.md` are ~1000 lines. Codex is struggling with file ordering. As tasks grow, this will only worsen — especially for tasks that span all 6 phases.

## Solution

Two mechanisms at different boundaries:

1. **Phase compaction** — before an agent's first write in a new phase, they replace their prior-phase content with a structured summary
2. **Within-phase round archival** — when round N >= 3, each agent moves rounds 1..N-2 out of their active file

## Design Principles

- **Ownership preserved**: each agent archives only their own content
- **Append-only spirit preserved**: archival moves content between files but never deletes it. The combination of active file + archive file preserves the complete history. This is explicitly permitted as the only exception to the "previous rounds MUST NOT be modified" rule.
- **Active files stay small**: at most 2 rounds of current phase + phase summary back-references
- **Summaries always loaded, raw rounds on-demand**: agents read phase summaries (top of archive) every round; raw archived rounds (bottom of archive) only when tracing a specific finding or decision

---

## Change 1: PROTOCOL.md

### 1a. Update Folder Structure (replace existing section)

```markdown
## Folder Structure

\```
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
\```
```

### 1b. Update File Ownership Rules (replace existing section)

```markdown
## File Ownership Rules

- Claude MUST NOT edit `judge.md` or `judge-archive.md`
- Codex MUST NOT edit `builder.md` or `builder-archive.md`
- Claude MAY respond to judge findings in a new round section of `builder.md`
- Codex MAY review that update in a new round section of `judge.md`
- Peter MAY edit any file
```

### 1c. Replace Round History section

```markdown
## Round History

Both `builder.md` and `judge.md` contain **only the current phase's recent rounds**. Older content lives in the corresponding archive file (`builder-archive.md`, `judge-archive.md`).

Within a phase, each round is a new section:

\```markdown
## Round 1 — design
...content...

## Round 2 — design
...content...
\```

Rounds in the active file MUST NOT be modified once written, except by the archival process described below.
```

### 1d. Add new section: Context Management (after Round History)

```markdown
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

\```markdown
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
\```

**Phase summary template** (judge):

\```markdown
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
\```

**Back-reference line** (placed at the top of the cleared active file):

\```markdown
<!-- Phase history: design (5 rounds, accepted), plan (4 rounds, accepted) — see [builder|judge]-archive.md -->
\```

### Within-Phase Round Archival

**Trigger (deterministic, from repo state):** Before writing a round, count the `## Round` headers in your active file. If there are 2 or more, and you are about to write Round N where N >= 3, archive the oldest rounds.

When archival is triggered, each agent MUST:

1. Move rounds 1 through N-2 from their active file to their archive file under a clearly labeled section
2. Leave the back-reference line and rounds N-1 onward in the active file

This ensures the active file contains at most 2 complete rounds plus the current work.

**Archive section header for moved rounds:**

\```markdown
## [design] Archived Rounds

### Round 1 — design (builder)
[original round content]

### Round 2 — design (builder)
[original round content]
\```

### Archive File Layout

Archive files MUST follow this layout — summaries at the top, raw rounds at the bottom:

\```markdown
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
\```

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
```

### 1e. Update Standard Loop (steps 2 and 4 — add context management)

In step 2, append: "Perform context management checks first: phase compaction if active file contains prior-phase rounds, round archival if active file has 2+ rounds and N >= 3 (see Context Management)."

In step 4, after "builder reads findings": "Perform context management checks before writing the new round."

---

## Change 2: CODEX.md

### 2a. Add step 2.5 to the judge workflow (between "Read context" and "Write judge.md")

```markdown
### 2.5. Context management

**Phase compaction check:** Read `judge.md` and find the first `## Round N — [phase]` header. Compare `[phase]` to the current phase in `status.json`. If they differ:
1. Write a phase summary for the completed phase to `judge-archive.md` using the judge phase summary template from `PROTOCOL.md`
2. Move your raw rounds from that phase to `judge-archive.md` under `## Raw Archived Rounds`
3. Clear `judge.md`, leaving only the back-reference comment line

If no round headers exist (empty or back-reference only), skip — compaction was already done.

**Round archival check:** Count `## Round` headers in `judge.md`. If there are 2 or more and you are about to write Round N where N >= 3:
1. Move rounds 1 through N-2 from `judge.md` to `judge-archive.md` under an archived rounds section
2. Keep the back-reference line and rounds N-1 onward
```

### 2b. Update step 2 ("Read context") to include archives

Add to the list:
```
7. Read the **Phase Summaries** section of `builder-archive.md` and `judge-archive.md` (if they exist) — this is required every round, not just on phase boundaries
```

### 2c. Replace "Append (never overwrite)" instruction (H-1 fix)

Replace the current instruction at CODEX.md line 32:
```
Append (never overwrite) a new section:
```
with:
```
Append a new section (previous rounds may only be moved to `judge-archive.md` via the Context Management process — never deleted or modified in place):
```

---

## Change 3: AGENTS.md

### 3a. Update Builder Quick Reference

Replace the current builder quick reference (AGENTS.md lines 101-106) with:

```markdown
**Builder (Claude Code):**
1. Read `task.md` for goal, scope, acceptance criteria
2. Read `judge.md` if it exists (previous round feedback)
3. Read **Phase Summaries** from both archive files (if they exist)
4. Perform context management checks (see PROTOCOL.md Context Management):
   - Phase compaction: if active file contains rounds from a prior phase, compact first
   - Round archival: if active file has 2+ rounds and you're writing round N >= 3, archive oldest
5. Append a new `## Round N — [phase]` section to `builder.md`
6. Update `status.json`: state -> `ready_for_judge`
7. Do NOT edit `judge.md` or `judge-archive.md`
```

### 3b. Update Judge Quick Reference

Replace the current judge quick reference (AGENTS.md lines 108-114) with:

```markdown
**Judge (Codex):**
1. Read `task.md` for goal, scope, acceptance criteria
2. Read `builder.md` (latest round)
3. Review any changed artifacts referenced by the builder
4. Read **Phase Summaries** from both archive files (if they exist)
5. Perform context management checks (see PROTOCOL.md Context Management):
   - Phase compaction: if active file contains rounds from a prior phase, compact first
   - Round archival: if active file has 2+ rounds and you're writing round N >= 3, archive oldest
6. Append a new `## Round N — [phase]` section to `judge.md` with verdict and findings
7. Update `status.json`: state -> verdict value
8. Do NOT edit `builder.md` or `builder-archive.md`
```

### 3c. Update File Ownership in Agent Loop section

Replace AGENTS.md line 96:
```
- Preserve append-only round history
```
with:
```
- Preserve round history — rounds may only be moved to archive files via the Context Management process, never deleted or modified in place
```

### 3d. Update Boundaries (replace existing, AGENTS.md lines 118-122)

Replace "Always do" (line 118):
```
**Always do:** Read `task.md` first. Use structured output from PROTOCOL.md. Use stable finding IDs (B-1, H-1, M-1, L-1). Append new rounds, never overwrite. Update `status.json` after writing. Check `agent-loop/ANTIPATTERNS.md` before finalizing each round.
```
with:
```
**Always do:** Read `task.md` first. Read Phase Summaries from archive files (if they exist). Use structured output from PROTOCOL.md. Use stable finding IDs (B-1, H-1, M-1, L-1). Perform context management checks before writing new rounds. Update `status.json` after writing. Check `agent-loop/ANTIPATTERNS.md` before finalizing each round.
```

Replace "Never do" (line 122):
```
**Never do:** Edit the other agent's artifact. Skip reading `task.md`. Overwrite previous rounds. Make product/scope decisions.
```
with:
```
**Never do:** Edit the other agent's artifact or archive. Skip reading `task.md`. Delete or modify rounds in place (archival via Context Management is the only permitted move). Make product/scope decisions.
```

---

## Change 4: CLAUDE.md

### 4a. Update Development Workflow section

Add under "Builder/Judge Roles":
```markdown
- Before writing a round, perform **context management checks** (see PROTOCOL.md):
  - **Phase compaction**: if `builder.md` contains rounds from a prior phase (compare round headers to `status.json` phase), write phase summary to `builder-archive.md`, move raw rounds there, clear `builder.md` to a back-reference line.
  - **Round archival**: if `builder.md` has 2+ round headers and you're writing round N >= 3, move rounds 1..N-2 to `builder-archive.md`.
- Read **Phase Summaries** from both archive files every round.
```

---

## Expected Impact

For task 001 at current state (18 rounds, 4 phases):

| Metric | Before | After |
|--------|--------|-------|
| `builder.md` lines | ~1069 | ~150 (2 test rounds) |
| `judge.md` lines | ~644 | ~80 (1 test round) |
| `builder-archive.md` | n/a | ~300 (3 phase summaries ~45 lines + raw archived rounds ~255 lines) |
| `judge-archive.md` | n/a | ~250 (3 phase summaries ~45 lines + raw archived rounds ~205 lines) |

**Context loaded per round (what matters for agent performance):**

| | Before | After |
|---|--------|-------|
| Active files (always loaded) | ~1713 lines | ~230 lines |
| Phase summaries (always loaded) | n/a | ~90 lines |
| Raw archived rounds (on-demand only) | n/a | ~460 lines (NOT loaded routinely) |
| **Total routine context** | **~1713 lines** | **~320 lines** |

**Reduction: ~81% less context loaded per round.**

The raw archived rounds exist for auditability but are only read when an agent needs to trace a specific finding or decision from a prior phase.

## CoVe Verification Record

### Round 1 (self-review)
1. **Timing ambiguity** → Fixed: compaction triggered "first time you write in a new phase," not on acceptance
2. **Append-only contradiction** → Fixed: explicitly noted as the only permitted exception, content moved not deleted
3. **Archive file structure** → Fixed: prescribed layout with Phase Summaries (always read) above Raw Archived Rounds (on-demand)
4. **Finding traceability** → No issue: N-2 window keeps finding/response pairs together in active files
5. **Archive file creation** → Fixed: explicitly stated "created on first use"
6. **Single-round phases** → No issue: compaction still applies, summary is just shorter
7. **Net context reduction** → Verified: ~1713 → ~320 lines routine context (81% reduction)
8. **Codex ordering struggle** → Directly addressed: fewer sections in active file = less to order

### Round 2 (Codex judge feedback)
1. **H-1: Contradictory "never overwrite" rules** → Fixed: explicitly replaced AGENTS.md lines 96, 118, 122 and CODEX.md line 32 with updated versions that permit archival-via-Context-Management as the only exception. No more dual directives.
2. **H-2: Inconsistent "when to read summaries"** → Fixed: unified to "every round" everywhere — design principle (line 25), reading rule (line 203), CODEX step 2b (line 253), AGENTS builder step 3 (line 267), AGENTS judge step 4 (line 281), AGENTS boundaries (line 310). All six references now say the same thing.
3. **M-1: Non-deterministic compaction trigger** → Fixed: replaced all "since your last round" / "if starting a new phase" with deterministic file-state checks. Phase compaction: compare round headers' `[phase]` to `status.json` phase. Round archival: count `## Round` headers in active file. Both are observable by any stateless agent without memory of prior sessions.

## Migration

For existing task 001:
- Not required immediately — the protocol change applies to future rounds
- Can optionally be applied retroactively by performing phase compaction for design, plan, and build phases before the next test round
- Recommended: builder performs retroactive compaction as part of the next round to give Codex immediate relief
