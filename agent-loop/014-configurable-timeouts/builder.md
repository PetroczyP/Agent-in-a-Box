# Builder: 014-configurable-timeouts

<!-- Phase history: build (2 rounds, accepted), test (3 rounds, accepted) — see builder-archive.md -->

## Round 6 — release

### Summary

Release readiness assessment for configurable review and discuss timeouts (issue #14). All acceptance criteria pass, 369 tests green, no regressions.

### Built vs Planned

| Scope Item (from task.md) | Status |
|---------------------------|--------|
| Add `review_timeout` and `discuss_timeout` constructor params to `ReviewEngine` | Done |
| Read `REVIEW_TIMEOUT` / `DISCUSS_TIMEOUT` env vars in `mcp_server.py` | Done |
| Update `docker-compose.yml` to document new env vars | Done |
| Update spec 001 FR-014 to reflect configurable timeouts | Done |

All 4 scope items complete. Nothing deferred or partially implemented.

### Files Changed (vs main)

```
 docker-compose.yml                 |  3 ++
 server/mcp_server.py               | 24 ++++++++++-
 server/review_engine.py            |  8 +++-
 specs/001-ai-code-reviewer/spec.md |  2 +-
 tests/test_review_engine.py        | 83 ++++++++++++++++++++++++++++++++++++++
 tests/test_mcp_server_config.py    | 53 ++++++++++++++++++++++++ (new)
 6 files changed, ~170 insertions, ~4 deletions
```

### Test Summary

```
$ pytest -v --tb=short
============================= 369 passed in 0.68s ==============================
```

| Test Group | Count | Status |
|------------|-------|--------|
| Existing tests (pre-change) | 355 | All pass |
| `TestConfigurableTimeouts` (review_engine) | 4 | All pass |
| `TestParseTimeout` (mcp_server_config) | 10 | All pass |
| **Total** | **369** | **All pass** |

### Acceptance Criteria Checklist

| AC | Description | Pass/Fail | Evidence |
|----|-------------|-----------|----------|
| AC-1 | Default review timeout = 120.0 | PASS | `test_review_uses_default_timeout` asserts `timeout=120.0` passed to `send_review` |
| AC-2 | Default discuss timeout = 60.0 | PASS | `test_discuss_uses_default_timeout` asserts `timeout=60.0` passed to `send_followup` |
| AC-3 | Custom review_timeout passed through | PASS | `test_review_uses_custom_timeout` with `review_timeout=200.0` |
| AC-4 | Custom discuss_timeout passed through | PASS | `test_discuss_uses_custom_timeout` with `discuss_timeout=90.0` |
| AC-5 | Env var overrides default | PASS | `test_valid_value` (int), `test_valid_float_value` (float) |
| AC-6 | Invalid env vars fall back gracefully | PASS | 8 tests: empty, negative, zero, non-numeric, inf, 1e999, -inf + `nan` also handled by `math.isfinite` |
| AC-7 | All 355+ existing tests pass | PASS | 369 total = 355 original + 14 new, zero failures |
| AC-8 | FR-014 updated in spec | PASS | `specs/001-ai-code-reviewer/spec.md` line 110 now reads configurable timeouts with env var names |

### Spec Success Criteria Cross-Reference

FR-014 (spec 001) is the only directly applicable requirement:
- **Before**: "System MUST enforce timeout budgets on Copilot SDK calls: 60 seconds for `start_review`, 30 seconds for `discuss`."
- **After**: "System MUST enforce configurable timeout budgets on Copilot SDK calls. Defaults: 120 seconds for `start_review` (configurable via `REVIEW_TIMEOUT` env var), 60 seconds for `discuss` (configurable via `DISCUSS_TIMEOUT` env var). Constructor arguments take precedence over env vars. On timeout, return a retryable error."
- Timeout error classification as retryable: unchanged, verified by existing `test_copilot_timeout_raises_retryable`

### Deferred Items

- Per-persona timeouts (spec 012 scope — does not block this release)
- Config module / config file (YAGNI — only 3 env vars total)
- Min/max validation ranges (YAGNI — self-correcting via immediate timeout on bad values)

### Known Limitations

- Default timeout values change from 60/30 to 120/60 for all users. This is intentional (research-backed) but is a behavior change for existing deployments.
- `copilot_client.py` default signatures still show 60.0/30.0 but are never used in practice (caller always passes explicit value). Updating them would be cosmetic.

### Tech Debt

- None introduced.

### Verification

- Checked: `git diff --stat main` confirms only the 6 expected files changed
- Checked: ANTIPATTERNS.md — no matches
- Corrections: None

### Remaining Risks

- None.

## Round 7 — release

### Summary

Fixed H-1: uncommented `REVIEW_TIMEOUT` and `DISCUSS_TIMEOUT` env vars in `docker-compose.yml` so they actually reach the container. Verified with `docker compose config`.

### Changes Since Last Round

- `docker-compose.yml` — Uncommented the two timeout env var lines so Compose passes them into the container

### Responses to Judge Findings

- H-1: Fixed. The env vars were commented out (documentation-only) and did not reach the container. Now uncommented as real pass-through entries with `${REVIEW_TIMEOUT:-120}` / `${DISCUSS_TIMEOUT:-60}` defaults. Verified:
  - `REVIEW_TIMEOUT=180 DISCUSS_TIMEOUT=90 docker compose config` → shows `REVIEW_TIMEOUT: "180"`, `DISCUSS_TIMEOUT: "90"` in environment
  - `docker compose config` (no env vars set) → shows `REVIEW_TIMEOUT: "120"`, `DISCUSS_TIMEOUT: "60"` (defaults applied)

### Test Evidence

```
$ pytest --tb=short
============================= 369 passed in 0.60s ==============================
```

### Verification

- Checked: `docker compose config` renders both timeout vars in the service environment
- Checked: Defaults (120/60) apply when host env vars are unset
- Checked: Custom values pass through when set on host
- Checked: ANTIPATTERNS.md — no matches
- Corrections: None

### Remaining Risks

- None.
