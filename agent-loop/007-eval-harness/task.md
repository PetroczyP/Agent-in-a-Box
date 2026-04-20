# Task: Eval Harness

**Task ID**: 007-eval-harness
**Origin**: specs/007-eval-harness/spec.md
**Phase**: specify
**Created**: 2026-03-31

## Goal

Build a repeatable, measurable evaluation framework that proves the AgentinaBox reviewer finds real issues (recall), doesn't invent fake issues (precision), and catches regressions when prompts, models, or bundle formats change. The harness runs a library of golden test cases through the live reviewer via MCP, grades findings using a multi-tier pipeline (deterministic fingerprint matching + model-based semantic grading), and produces a scorecard with actionable metrics.

## Scope

- **US1 (P1)**: Run eval suite against 20+ golden test cases, compare findings to expected findings, produce scorecard with precision, recall, severity accuracy, category accuracy, SNR, pass@k
- **US2 (P2)**: Grade multi-turn discussion quality — verify reviewer appropriately accepts/rejects rebuttals, compute rebuttal accuracy metric
- **US3 (P3)**: Measure false positive rate on clean code — BUG/WARN findings on correct code should be < 20%
- **US4 (P4)**: CI regression testing — eval runs automatically on prompt/parser changes, fails build if metrics drop below thresholds, posts scorecard as PR comment

**Out of Scope** (belongs to other specs):
- Feedback harvesting from deployed instances (moved to spec 003)
- Web UI for eval results (spec 003 dashboard territory)
- Usefulness Rate / acceptance rate metric (requires production usage tracking)
- Saturation monitoring (future enhancement)

## Constraints (from constitution)

1. **Project-Agnostic**: The eval harness tests the reviewer's MCP interface, not repo-specific code. Golden cases are self-contained fixtures, not references to external repos.
2. **No Volume Mounts**: Eval sends context via MCP parameters (same as production). No filesystem shortcuts.
3. **Test-First (TDD)**: RED-GREEN-REFACTOR. Write failing test before implementation for every component.
4. **Simplicity (YAGNI)**: CLI tool with markdown + JSON output. No web UI, no database, no React. Fixtures are directories on disk.
5. **Live Instance Testing**: Eval runs against a real AgentinaBox Docker instance (FR-008). No mocking the inner model.

## Acceptance Criteria

- **AC-1**: Eval suite runs 20+ golden cases and produces a scorecard within 30 minutes (SC-001)
- **AC-2**: Eval correctly detects regression when reviewer system prompt is degraded (SC-002)
- **AC-3**: False positive rate on clean code cases is measurably below 20% (SC-003)
- **AC-4**: Developer can add a new golden case by creating a directory with diff + expected.json — no code changes required (SC-004)
- **AC-5**: Eval suite runs in CI mode (`--ci`) and exits with code 0/1 based on thresholds (SC-005)
- **AC-6**: Multi-turn eval cases test rebuttal handling with scripted discuss sequences
- **AC-7**: Scorecard reports both pass@1 and pass@3 metrics alongside averages with SEM
- **AC-8**: Dual-metric cases test both vulnerable and fixed versions of bug-fix PRs
- **AC-9**: All existing tests continue to pass (no regressions)
- **AC-10**: Findings that don't match via fingerprint are forwarded to a model-based grader that classifies them as match/partial_match/novel_valid/no_match using a structured rubric with few-shot examples
- **AC-11**: Model-based grader uses a different model than the one being evaluated
- **AC-12**: Grader prompt version is recorded in eval run metadata

## Open Decisions

- Exact directory structure for eval package (eval/ vs tests/eval/)
- Whether golden cases live inside the repo or in a separate fixtures directory
- MCP transport mechanism for eval runner (docker exec stdio vs subprocess)
- Which model to use as Tier 2 grader (must differ from the model being evaluated — design phase decision)

## Spec Path

`specs/007-eval-harness/spec.md`
