# Task: Configurable Review & Discuss Timeouts (Issue #14)

**Task ID**: 014-configurable-timeouts
**Owner**: Peter
**Created**: 2026-03-19
**Phase**: build
**Spec**: `specs/001-ai-code-reviewer/spec.md` (FR-014 update)

## Goal

Make the hardcoded 60s (`start_review`) and 30s (`discuss`) Copilot SDK call timeouts configurable via environment variables, with research-backed increased defaults (120s / 60s).

## Scope

- Add `review_timeout` and `discuss_timeout` constructor params to `ReviewEngine`
- Read `REVIEW_TIMEOUT` / `DISCUSS_TIMEOUT` env vars in `mcp_server.py` (composition root)
- Update `docker-compose.yml` to document the new env vars
- Update spec 001 FR-014 to reflect configurable timeouts

## Out of Scope

- Per-persona timeouts (spec 012)
- Config module / config file approach
- Min/max validation ranges
- Changes to `copilot_client.py` default signatures

## Constraints

- TDD: write failing tests before implementation
- Env var reading in composition root, not in ReviewEngine (testability)
- No new dependencies
- Backwards compatible: existing users with no env vars get new defaults (intentional improvement)

## Acceptance Criteria

- AC-1: `ReviewEngine()` with no timeout args passes `timeout=120.0` to `send_review`
- AC-2: `ReviewEngine()` with no timeout args passes `timeout=60.0` to `send_followup`
- AC-3: `ReviewEngine(review_timeout=X)` passes `timeout=X` to `send_review`
- AC-4: `ReviewEngine(discuss_timeout=X)` passes `timeout=X` to `send_followup`
- AC-5: `REVIEW_TIMEOUT` env var overrides the default when passed through `mcp_server.py`
- AC-6: Invalid env var values (empty, negative, non-numeric) fall back to defaults gracefully
- AC-7: All 355+ existing tests continue to pass
- AC-8: FR-014 in spec 001 updated to reflect configurable timeouts

## Open Decisions

None — approach agreed in plan.
