# Requirements Quality Checklist — 007-eval-harness

**Generated**: 2026-03-31
**Spec version**: Draft (enhanced with research findings + multi-tier grading)

## Structure Completeness

- [x] User scenarios with priorities (P1-P4) and acceptance scenarios
- [x] Functional requirements (FR-001 through FR-022, plus FR-012a) — testable, unambiguous
- [x] Key entities with fields and relationships (7 entities including Grader Result, Grader Prompt)
- [x] Success criteria (SC-001 through SC-005) — measurable, technology-agnostic
- [x] Edge cases documented (5 scenarios)
- [x] Research & best practices section with sourced references

## Requirement Quality

- [x] No implementation details in requirements (e.g., FR-005 specifies matching behavior, not algorithm)
- [x] All requirements are testable — each FR can be verified with a concrete test
- [x] Success criteria are measurable — SC-001 has time bound, SC-002 has observable regression, SC-003 has numeric threshold
- [x] All thresholds have explicit default values (precision >= 70%, recall >= 60%, etc.)
- [x] Tolerance values are specified (line matching: +/- 5 lines, FR-005)
- [x] Scoring contract for `novel_valid` findings is explicit (FR-021 table) — no ambiguity in metric computation

## Dependency & Scope

- [x] Single dependency: spec 001 (core review server)
- [x] No circular dependencies
- [x] US5 (feedback harvesting) moved to spec 003 — no external dependency
- [x] Out-of-scope items explicitly listed (web UI, usefulness rate, saturation monitoring)
- [x] Interaction with spec 012 documented (dimension coverage metric)

## Multi-Tier Grading (FR-018 through FR-022)

- [x] Two-tier pipeline specified: deterministic (Tier 1) + model-based (Tier 2)
- [x] Routing rule is unambiguous: Tier 1 resolves fingerprint matches entirely (including severity/category accuracy); only non-matches go to Tier 2
- [x] Tier 2 prompt requirements specified (rubric, few-shot examples, structured JSON output)
- [x] Grader model independence required (FR-020) — different model than evaluated
- [x] Four-way classification with explicit scoring contract table (FR-021)
- [x] Grader prompt versioning required (FR-022)

## Research-Backed Additions

- [x] SNR metric added (FR-004 table) — sourced from CR-Bench findings
- [x] pass@1 metric added (FR-004 table, FR-017) — sourced from OpenAI evals
- [x] Dual-metric testing (FR-015) — sourced from DeepSource benchmark
- [x] Statistical reporting with SEM and confidence intervals (FR-016) — sourced from Anthropic eval guide
- [x] Nondeterminism handling specified (FR-011, FR-017) — multiple trials with aggregation
- [x] Multi-tier grading (FR-018-022) — sourced from Anthropic eval training, CR-Bench, Martian benchmark

## CI Integration Traceability

- [x] US4 requires CI regression testing with PR comment posting
- [x] FR-010 specifies `--ci` mode with exit codes
- [x] FR-012a specifies markdown scorecard output suitable for PR comment posting (before/after comparison)
- [x] SC-005 requires CI run + PR comment capability
- [x] Responsibility boundary clear: harness outputs markdown, CI pipeline posts it

## Edge Case Coverage

- [x] Non-deterministic responses (multiple trials, pass@k)
- [x] Valid findings not in expected set (`novel_valid` classification with explicit scoring contract)
- [x] Partially correct findings (line tolerance + `partial_match` via Tier 2)
- [x] Rate limiting during eval (backoff + retry, FR-013)
- [x] Dual-metric scoring when both versions trigger findings

## Constitution Compliance

- [x] Project-agnostic: golden cases are self-contained, no repo references
- [x] No volume mounts: eval uses MCP parameters, same as production
- [x] Test-first: TDD specified in constitution, applicable to build phase
- [x] Simplicity: CLI + markdown/JSON output, no database, no web UI
- [x] Live instance testing (FR-008): no mocking the inner model

## Resolved Clarifications

- [x] Golden case directory layout: per-case directory under `eval/fixtures/golden_cases/<case_id>/` with `meta.json`, `expected.json`, `bundle/diff.patch`, `bundle/files/` (URL-encoded filenames). See `eval/loader.py` and `specs/007-eval-harness/data-model.md`.
- [x] MCP transport: `docker exec -i <container> python -m server.mcp_server` via stdio (`eval/mcp_client.py:connect`).
- [x] Golden case location: dedicated `eval/fixtures/` directory inside the repo (checked into git; see `data-model.md`).
- [x] Tier 2 grader model: Anthropic Claude Sonnet (`claude-sonnet-4-6`) as the default, overridable with `--grader-model` (`eval/graders/__init__.py:DEFAULT_GRADER_MODEL`).
