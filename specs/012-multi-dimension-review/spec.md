# Feature Specification: Multi-Dimension Review Engine

**Feature Branch**: `012-multi-dimension-review`
**Created**: 2026-03-16
**Status**: Draft
**Depends on**: 001-ai-code-reviewer, 008-prompt-tuning
**Interacts with**: 005-model-configuration (per-review model override applies to all persona calls)

## Problem Statement

LLM-based code reviewers suffer from a well-documented "drip-feed discovery" problem: they find some issues on the first pass, then find different issues on subsequent passes — issues they could have found the first time. The root causes are:

1. **Attention distribution** — LLMs have limited attention budget and gravitate toward the most salient issues first, leaving subtler ones for "next time."
2. **Single-persona bias** — One reviewer with one system prompt has natural blind spots. A correctness-focused pass misses security; a style-focused pass misses design.
3. **No structured coverage guarantee** — Without a checklist, the model free-associates and may deeply analyze some functions while skimming others.
4. **Context fragmentation** — Large diffs reviewed as a single blob lose cross-file relationships.

This spec replaces the single-pass review with a multi-persona parallel review that forces systematic coverage across all review dimensions.

## Industry Context

- **GitHub Copilot** (March 2026) rebuilt their code review on an agentic architecture with tool calling, cross-review memory, and deterministic tool integration (CodeQL, ESLint).
- **CodeRabbit** uses a multi-layered approach with adaptive review depth, vector-indexed knowledge graphs, and incremental learning from feedback.
- **Research** on multi-AI code review shows that a 5-dimensional analysis (security, performance, maintainability, correctness, style) with ensemble consensus outperforms single-pass review.

AgentinaBox can't match GitHub's native repo-exploration advantage (we receive context via MCP, not tool calling into the repo). But we can match or exceed their review thoroughness by running multiple specialized passes with forced coverage checklists — something a single-pass reviewer architecturally cannot do.

## User Scenarios & Testing

### User Story 1 - Thorough First-Pass Review (Priority: P1)

Claude Code sends a review bundle via MCP `start_review` with `review_mode: "thorough"`. The review server dispatches the bundle to 4 specialized reviewer personas in parallel (correctness, security, design, tests). Each persona reviews the code through its specific lens with a mandatory checklist. A synthesis step merges, deduplicates, and cross-references the findings. Claude Code receives a single unified finding set that is significantly more comprehensive than a single-pass review.

**Why this priority**: This is the core value proposition — eliminating the drip-feed discovery problem. A developer should be able to trust that the first review caught the important issues across all dimensions.

**Independent Test**: Send a review bundle containing a known bug (e.g., SQL injection), a design issue (e.g., tight coupling), and a test gap (e.g., untested error path) via `start_review` with `review_mode: "thorough"`. Verify that findings cover all three dimensions — not just the most obvious one.

**Acceptance Scenarios**:

1. **Given** a diff with a security vulnerability (unsanitized input) AND a correctness bug (off-by-one) AND a missing test, **When** `start_review` is called with `review_mode: "thorough"`, **Then** the response contains findings from at least 3 different categories (security, correctness, tests).
2. **Given** a diff with no issues, **When** `start_review` is called with `review_mode: "thorough"`, **Then** the response is an empty finding set (personas agree there are no issues).
3. **Given** two personas identify the same issue at the same location, **When** findings are synthesized, **Then** a single finding is returned with the higher severity and merged evidence from both personas.
4. **Given** `start_review` is called with `review_mode: "thorough"`, **When** the review completes, **Then** each finding includes a `source_persona` field indicating which persona(s) identified it.

---

### User Story 2 - Standard Single-Pass Review (Priority: P1)

Claude Code sends a review bundle via MCP `start_review` with `review_mode: "standard"` (or omits the parameter). The review server uses the existing single-pass flow — one model call, one finding set. This preserves backward compatibility and provides a fast/cheap option for quick reviews.

**Why this priority**: Equal to P1 because backward compatibility is non-negotiable. Existing MCP clients must work without changes.

**Independent Test**: Call `start_review` without `review_mode` parameter. Verify the response matches the existing single-pass behavior exactly.

**Acceptance Scenarios**:

1. **Given** `start_review` is called without `review_mode`, **When** the review completes, **Then** behavior is identical to the pre-012 single-pass flow.
2. **Given** `start_review` is called with `review_mode: "standard"`, **When** the review completes, **Then** behavior is identical to omitting the parameter.

---

### User Story 3 - Focused Multi-Dimension Review (Priority: P2)

Claude Code wants a multi-dimension review but only cares about specific dimensions (e.g., security and correctness for a sensitive change). It calls `start_review` with `review_mode: "focused"` and `personas: ["security", "correctness"]`. Only the specified personas run, reducing cost and latency while still providing targeted multi-dimension coverage.

**Why this priority**: Power-user feature that adds cost flexibility. Not needed for MVP but valuable for CI/CD integration where token cost matters.

**Independent Test**: Call `start_review` with `review_mode: "focused"` and `personas: ["security"]`. Verify only security-related findings are returned.

**Acceptance Scenarios**:

1. **Given** `start_review` is called with `review_mode: "focused"` and `personas: ["security", "correctness"]`, **When** the review completes, **Then** only the security and correctness personas run, and findings are tagged accordingly.
2. **Given** `start_review` is called with `review_mode: "focused"` and an invalid persona name, **When** the request is validated, **Then** the server returns a clear error listing valid persona names.

---

### User Story 4 - Meta-Review for Coverage Gaps (Priority: P3)

After the persona findings are synthesized, an optional meta-review pass checks whether any review dimension is under-represented. If the correctness persona found 5 issues but the security persona found 0, the meta-reviewer asks: "Is this code genuinely secure, or did the security pass miss something?" This catches the "focused on 3 functions, skimmed 7" failure mode.

**Why this priority**: Enhancement on top of the core multi-dimension approach. Valuable for high-stakes reviews but adds latency and cost.

**Independent Test**: Send a review bundle where one persona returns many findings and another returns none. Verify the meta-review flags the coverage imbalance.

**Acceptance Scenarios**:

1. **Given** a thorough review where 3 personas return findings but 1 returns none, **When** meta-review is enabled, **Then** the meta-reviewer produces either a `coverage-gap` finding citing the empty dimension, or a confirmation note in the findings metadata that the dimension was evaluated and found clean.
2. **Given** meta-review identifies a potential gap, **When** findings are returned, **Then** a finding with `rule_id: coverage-gap` and `severity: WARN` is included, citing the under-represented dimension.

---

### Edge Cases

- What happens when one persona times out but others complete successfully?
  - Return findings from completed personas. Include a `coverage-gap` finding noting the timed-out persona. Do not fail the entire review.
- What happens when all personas return zero findings?
  - Valid outcome. Return empty finding set. If meta-review is enabled, it confirms the clean result.
- What happens when personas produce contradictory findings (one says "this is fine", another says "this is a bug") at the same location?
  - Synthesis keeps the higher-severity finding and includes both perspectives in the evidence field. The meta-reviewer can be asked to arbitrate.
- What happens when the review bundle is too large for parallel persona calls?
  - Each persona gets the same bundle. If the bundle exceeds the model's context window, fail fast with the existing FR-009 error (from spec 001). Do not attempt to split the bundle across personas differently.
- What happens when `review_mode: "thorough"` is used with `discuss`?
  - Discussion rounds use single-pass mode regardless of the initial `review_mode`. Multi-dimension is for the initial analysis; discussion is conversational.
- How does this interact with per-review model override (spec 005)?
  - All personas use the same model. The `model` parameter from spec 005 applies to all persona calls and the synthesis call.

## Requirements

### Functional Requirements

#### Orchestration

- **FR-001**: System MUST support three review modes via `start_review` parameter: `"standard"` (single-pass, default), `"thorough"` (all personas), and `"focused"` (selected personas)
- **FR-002**: System MUST dispatch persona reviews in parallel and merge results via a synthesis step
- **FR-003**: System MUST maintain backward compatibility with the existing MCP interface. `review_mode` and `personas` are additive optional parameters on `start_review`. Omitting them MUST produce identical behavior to pre-012
- **FR-004**: System MUST enforce a configurable timeout per persona call, independent of the overall `start_review` timeout (FR-014 in spec 001). Default: 60 seconds per persona

#### Personas

- **FR-005**: System MUST ship with 4 built-in personas: `correctness`, `security`, `design`, `tests`. Persona names align with the existing `Category` enum values in `server/models.py`
- **FR-006**: Each persona MUST have a dedicated system prompt with: (a) a focused review mandate describing the persona's domain, (b) a mandatory checklist of items the persona must evaluate before returning findings, (c) the same structured JSON output format as spec 008. Personas are NOT constrained to their own category — a `security` persona may emit a `correctness` finding if it discovers a bug while tracing a security issue. The `source_persona` field tracks which persona produced the finding; the `category` field reflects the finding's nature
- **FR-007**: System SHOULD support an optional 5th persona (`performance`) that is disabled by default and enabled via configuration or `personas` parameter. Findings from the `performance` persona use `category: maintainability` since the existing `Category` enum does not include `performance`. If a dedicated `performance` category is needed, the enum extension is deferred to a future spec
- **FR-008**: Persona system prompts MUST be stored as separate, documented templates (not inline strings) for maintainability

#### Synthesis

- **FR-009**: System MUST merge findings from all personas into a single unified finding set
- **FR-010**: System MUST deduplicate findings with matching `fingerprint` values (the existing hash field on Finding, computed from `rule_id` + normalized code at `primary_location`). When duplicates exist, keep the highest severity and merge evidence from all sources
- **FR-011**: System MUST tag each finding with a `source_persona` field (string or list of strings if multiple personas found the same issue)
- **FR-012**: System SHOULD cross-reference findings at the same location from different personas and link them as `related_locations`

#### Meta-Review (Optional)

- **FR-013**: System SHOULD support an optional meta-review pass after synthesis. When enabled, a final LLM call evaluates the combined finding set for coverage gaps across dimensions
- **FR-014**: Meta-review findings MUST use `rule_id: coverage-gap` and include the under-represented dimension in the message

#### Resilience

- **FR-015**: If one or more personas fail (timeout, error), System MUST return findings from the successful personas and include a `coverage-gap` finding for each failed persona. The review MUST NOT fail entirely unless all personas fail
- **FR-016**: System MUST log per-persona timing, finding count, and success/failure status for observability
- **FR-017**: System MUST use single-pass review mode for all `discuss` calls regardless of the session's original `review_mode`. Multi-dimension orchestration applies only to the initial `start_review` analysis

#### Token Accounting

- **FR-018**: System MUST track `TokenUsage` per persona call and roll up to the session-level total. The per-persona breakdown MUST be available via `get_review_summary` for cost visibility

### Key Entities

- **ReviewOrchestrator** (new): Orchestration layer between `mcp_server.py` and `review_engine.py`. Dispatches persona calls, collects results, invokes synthesis. Lives in `server/review_orchestrator.py`.

- **ReviewPersona** (new): Configuration object for a reviewer persona. Contains: `name` (e.g., "correctness"), `system_prompt` (the persona-specific review instructions + checklist), `enabled` (default on/off). Lives in `server/personas/`.

- **FindingSynthesizer** (new): Merges, deduplicates, and cross-references findings from multiple persona passes. Lives in `server/finding_synthesizer.py`.

- **ReviewBundle** (extended): Existing Pydantic model from spec 001. Adds two optional fields: `review_mode: ReviewMode | None = None` and `personas: list[str] | None = None`. Backward-compatible — omitting both preserves pre-012 behavior.

- **Finding** (extended): Existing entity from spec 001. Adds `source_persona: str | list[str] | None` field. This is a SARIF extension property (carried in the SARIF `properties` bag), not a core SARIF field. Backward-compatible (defaults to `None` for single-pass reviews).

- **ReviewMode** (new): Enum with values `standard`, `thorough`, `focused`. Passed as optional parameter to `start_review`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: For a curated test set of 5+ code samples each containing issues across 3+ review dimensions, `thorough` mode finds issues in >= 3 dimensions on the first pass
- **SC-002**: `thorough` mode wall-clock latency is <= 2x the latency of `standard` mode. Measured with a mock backend that introduces a configurable per-call delay, verifying that 4-persona parallel mode completes in <= 2x the single-call delay
- **SC-003**: Finding deduplication produces zero duplicate findings (same fingerprint) in the unified output
- **SC-004**: `standard` mode (default) produces identical results to pre-012 behavior — zero regressions in existing test suite
- **SC-005**: Each persona's mandatory checklist is verifiable: persona output references checklist items or the meta-review flags incomplete checklists
- **SC-006**: When one persona times out, the review still returns findings from the remaining personas within the overall timeout budget
