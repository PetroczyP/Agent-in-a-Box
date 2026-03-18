# Feature Specification: Cross-Session Review Memory

**Feature Branch**: `013-review-memory`
**Created**: 2026-03-16
**Status**: Backlog (Draft)
**Depends on**: 001-ai-code-reviewer, 012-multi-dimension-review

## Summary

Enable AgentinaBox to remember findings, dismissals, and patterns across review sessions. The system builds project-specific review intelligence over time: detecting regressions (a previously-fixed issue reappearing), respecting dismissals (not re-flagging issues the human already rejected), and surfacing recurring patterns ("this project's top 3 issues are...").

## Motivation

Currently all review state is ephemeral (FR-015 in spec 001). Every review starts from zero. This means:

- A dismissed finding gets re-flagged next PR
- A fixed-then-reintroduced bug isn't flagged as a regression
- The reviewer can't learn that "this project struggles with error handling"
- The dashboard (spec 003) can't show historical trends

GitHub Copilot added [repository-specific agentic memory](https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/) in January 2026 (public preview) with 28-day auto-expiry. CodeRabbit uses a vector-indexed knowledge graph that learns from developer feedback. This spec brings comparable capability to AgentinaBox.

## Key Capabilities (to be specified)

1. **Finding persistence** — Store finding fingerprints, statuses, and dismissal reasons across sessions
2. **Regression detection** — Flag when a previously-fixed finding's fingerprint reappears
3. **Dismissal memory** — When a human dismisses a finding (spec 004), remember the dismissal so the same fingerprint isn't re-flagged
4. **Pattern analysis** — Surface recurring rule_ids, categories, and severity distributions over time
5. **Memory expiry** — Auto-expire stale memories (configurable, default 28 days per GitHub's precedent)

## Open Questions

- What storage backend? SQLite in the Docker volume (consistent with constitution's simplicity principle) vs. a more structured approach?
- What exactly gets persisted? Fingerprints + metadata are safe. Code snippets in `evidence` fields raise security boundary questions (constitution Principle III).
- How does memory interact with the content denylist? Finding evidence may quote code — should it be filtered before persistence?
- Should memory be per-project (identified by what?) or global across all reviews?
- How does memory import/export work for team sharing?
- What's the privacy model? Can a user delete all memories? GDPR considerations?

## Rough User Stories

### US1 - Regression Detection (P1)

A finding with fingerprint X was flagged in PR #10, developer fixed it. In PR #15, the same fingerprint reappears. The reviewer flags it as `rule_id: regression` with a reference to the original session.

### US2 - Dismissal Memory (P1)

A human dismissed finding F-003 in PR #10 with reason "intentional design choice." In PR #12, the same fingerprint appears. The reviewer skips it (or flags it as `severity: NIT` with "previously dismissed: intentional design choice").

### US3 - Project Health Dashboard (P2)

The dashboard (spec 003) shows a "Review Intelligence" panel: top 5 recurring issue types, finding trend over time, fix rate, regression rate.

### US4 - Memory Management (P2)

A user can view, search, and delete stored memories via the web UI. Memories auto-expire after a configurable period.
