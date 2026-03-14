---
description: "Builder/judge protocol: create new tasks, continue existing ones, or advance phases. Usage: /loop.build new <description>, /loop.build <task-id> [phase], /loop.build (auto-detect)"
---

## User Input

```text
$ARGUMENTS
```

## Instructions

You are the **builder** in the builder/judge protocol. Read `agent-loop/PROTOCOL.md` for the full rules. Never edit `judge.md`.

This skill integrates the speckit workflow. Each phase delegates to the appropriate speckit process internally while wrapping it in the builder/judge loop.

---

### Step 1: Parse the command

Parse `$ARGUMENTS` to determine the mode:

| Input pattern | Mode | Example |
|--------------|------|---------|
| `new <description>` | **Create** a new task | `/loop.build new Dockerized AI code review server` |
| `<task-id> <phase>` | **Advance** to a new phase | `/loop.build 001-ai-code-reviewer plan` |
| `<task-id>` | **Continue** the current phase | `/loop.build 001-ai-code-reviewer` |
| _(empty)_ | **Auto-detect** most recent task | `/loop.build` |

For auto-detect: find the most recently modified `status.json` under `agent-loop/*/`.

---

### Step 2: Handle each mode

#### Mode: CREATE (`new`)

1. Determine the next available task number by scanning existing `agent-loop/NNN-*/` folders
2. Generate a short kebab-case name from the description (e.g., "core-review-server")
3. Create the folder: `agent-loop/NNN-short-name/`
4. Check if a matching spec already exists in `specs/` (by name similarity)
5. Write `task.md` with:
   - Goal (from the description)
   - Scope (from matching spec if found, otherwise infer from description)
   - Constraints (from constitution at `.specify/memory/constitution.md`)
   - Acceptance criteria (from matching spec if found, otherwise draft from description)
   - Phase: `specify`
   - Open decisions (flag anything ambiguous)
   - Spec path (if a matching spec exists, reference it)
6. Write `status.json` with state `ready_for_builder`, phase `specify`, round 1
7. **Then immediately proceed to the CONTINUE flow below** for the `specify` phase

#### Mode: ADVANCE (`<task-id> <phase>`)

1. Read `status.json` — verify current phase is `accepted` or that user is explicitly requesting phase change
2. Update `status.json`: set `phase` to the new phase, reset `round` to 1, set state to `ready_for_builder`
3. Reset `verdict` to null
4. **Then immediately proceed to the CONTINUE flow below**

Valid phases in order: `specify` → `design` → `plan` → `build` → `test` → `release`

#### Mode: CONTINUE (default)

This is the core builder loop. Read the task context and produce output appropriate for the current phase.

---

### Step 3: Read task context

1. Read `task.md` — goal, scope, constraints, acceptance criteria, spec path
2. Read `status.json` — current phase, round, state
3. If `judge.md` exists, read the **latest round** — note every finding by ID (B-1, H-1, M-1, L-1)
4. If the state is `accepted` and no phase override was given, tell the user the current phase is done and suggest the next phase

---

### Step 4: Do phase-appropriate work

Each phase integrates speckit's structured process. The builder does the speckit work AND records it in `builder.md`.

#### Phase: `specify` — Feature Specification

**Speckit equivalent**: `/speckit.specify`

1. Read `.specify/templates/spec-template.md` for required structure
2. Read `.specify/memory/constitution.md` for project principles
3. If a spec already exists (referenced in `task.md`), read it as the starting point
4. If no spec exists:
   - Create `specs/NNN-feature-name/` directory
   - Draft the spec following the template structure
5. The spec MUST include:
   - User scenarios with priorities (P1, P2, P3) and acceptance scenarios
   - Functional requirements (testable, unambiguous)
   - Key entities with fields and relationships
   - Success criteria (measurable, technology-agnostic)
   - Edge cases
6. Generate a quality checklist at `specs/NNN-feature-name/checklists/requirements.md`:
   - Validate: no implementation details, requirements testable, success criteria measurable, all mandatory sections complete
   - Max 3 `[NEEDS CLARIFICATION]` markers — only for critical ambiguities
7. Write/update the spec file at `specs/NNN-feature-name/spec.md`

**Builder.md records**: spec path, checklist results, any clarifications needed, remaining risks

#### Phase: `design` — Technical Design & Research

**Speckit equivalent**: `/speckit.plan` (Phase 0: Research + Phase 1: Design & Contracts)

1. Run `.specify/scripts/bash/setup-plan.sh --json` to initialize the plan structure
2. Read the spec and constitution
3. **Phase 0 — Research**:
   - Identify unknowns and technical decisions
   - Research best practices for each technology choice
   - Consolidate findings in `{feature-dir}/research.md` (Decision / Rationale / Alternatives format)
4. **Phase 1 — Design & Contracts**:
   - Extract entities from spec → `{feature-dir}/data-model.md`
   - Define interface contracts → `{feature-dir}/contracts/`
   - Fill Technical Context and Constitution Check in plan.md
   - Evaluate constitution gates — ERROR if violations are unjustified
5. Run `.specify/scripts/bash/update-agent-context.sh claude` to update agent context

**Builder.md records**: design decisions, constitution compliance, research findings, data model summary, contract overview

#### Phase: `plan` — Implementation Tasks

**Speckit equivalent**: `/speckit.tasks`

1. Run `.specify/scripts/bash/check-prerequisites.sh --json` to verify available docs
2. Read: plan.md (required), spec.md (required), data-model.md (if exists), contracts/ (if exists), research.md (if exists)
3. Generate `{feature-dir}/tasks.md` following `.specify/templates/tasks-template.md`:
   - **Phase 1**: Setup (project initialization)
   - **Phase 2**: Foundational (blocking prerequisites)
   - **Phase 3+**: One phase per user story in priority order
   - **Final Phase**: Polish & cross-cutting
4. Every task MUST use the strict checklist format:
   ```
   - [ ] [TaskID] [P?] [Story?] Description with file path
   ```
   - `T001`, `T002`, etc. in execution order
   - `[P]` marker if parallelizable
   - `[US1]`, `[US2]` etc. for user story tasks
5. Include: dependency graph, parallel execution opportunities, MVP scope suggestion

**Builder.md records**: task count, phases, parallel opportunities, MVP scope, dependency summary

#### Phase: `build` — Implementation

**Speckit equivalent**: `/speckit.implement`

1. Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks`
2. Check checklists status in `{feature-dir}/checklists/` — report pass/fail table
3. Load: tasks.md, plan.md, data-model.md, contracts/, research.md
4. Execute tasks phase by phase:
   - Respect dependency order: sequential tasks in order, `[P]` tasks can parallelize
   - Follow TDD per constitution: write failing test → implement → refactor
   - Mark completed tasks as `[X]` in tasks.md
5. Create/verify ignore files (.gitignore, .dockerignore, etc.) based on tech stack
6. Report progress after each completed task
7. Halt on non-parallel task failure; continue parallel tasks and report failures

**Builder.md records**: tasks completed (with IDs), test commands run and results, files changed, any blockers hit

#### Phase: `test` — Verification & Hardening

**No speckit equivalent** — this is builder/judge specific.

1. Run full test suite and record results verbatim
2. Check coverage — identify untested paths
3. Add edge case tests for scenarios from spec's Edge Cases section
4. Run linting / type checking if applicable
5. Verify all acceptance criteria from `task.md` can be demonstrated

**Builder.md records**: test output, coverage metrics, edge cases added, AC verification results

#### Phase: `release` — Final Readiness

**No speckit equivalent** — this is builder/judge specific.

1. Summarize what was built vs. what was planned (tasks.md completion status)
2. List all tests and their pass/fail status
3. Check every acceptance criterion from `task.md` — mark pass/fail with evidence
4. Cross-reference against the spec's Success Criteria
5. Note any deferred items, known limitations, or tech debt
6. Confirm Docker build and `docker compose up -d` works (if applicable)

**Builder.md records**: AC checklist, test summary, deferred items, deployment verification

---

### Step 5: Write builder.md

Determine the round number:
- If `builder.md` doesn't exist: Round 1
- Otherwise: increment from the last round in the file

Append (never overwrite) a new section:

```markdown
## Round N — [phase]

### Summary
- ...

### Speckit Artifacts
- [list files created/updated by speckit process this round]
(omit if no speckit artifacts were produced)

### Changes Since Last Round
- ... (omit for Round 1)

### Design / Implementation Notes
- ...

### Test Evidence
- ... (omit if no tests yet)

### Responses to Judge Findings
- H-1: addressed by ...
- M-2: declined because ...
(omit for Round 1 or if no judge.md exists)

### Verification
- Checked: [what was web-searched or CoVe self-verified]
- Corrections: [what changed as a result, or "None"]

### Remaining Risks
- ...
```

Rules:
- **Append only** — never modify previous rounds
- Respond to **every** judge finding using their IDs
- If declining a finding, state the reason
- Include evidence: spec references, test output, diffs
- Make deltas easy to review — the judge should not need to re-read everything

### Verification step (between Step 4 and Step 5)

Before writing builder.md, run Chain of Verification:

1. **Question**: Generate 3-5 verification questions about your own output — targeting factual claims about external tools, SDKs, APIs, library behavior, or compatibility
2. **Web search**: For each question involving an external tool or API, search current documentation. Do not rely solely on training data.
3. **Revise**: Fix any inconsistencies. Record what was checked and corrected in the `### Verification` section of builder.md.

This is mandatory for `specify`, `design`, and `build` phases. Optional for `test` and `release` where the code itself is the verification.

---

### Step 6: Update status.json

- Set `state` to `"ready_for_judge"`
- Update `round` to the current round number
- Update `updated_at` to current ISO timestamp
- Append to `history`: `{ "round": N, "phase": "<phase>", "actor": "builder", "verdict": null, "timestamp": "..." }`

---

### Step 7: Report to the user

Tell the user concisely:
- Task ID and phase
- Round number
- What you produced or changed (files list)
- That it's ready for the judge
- Suggest: "Send to Codex with `judge NNN-task-name`"
