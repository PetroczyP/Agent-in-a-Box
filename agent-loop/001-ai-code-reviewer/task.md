# Task: Core Review Server (Spec 001)

**Task ID**: 001-ai-code-reviewer
**Owner**: Peter
**Created**: 2026-03-13
**Phase**: design
**Spec**: `specs/001-ai-code-reviewer/spec.md`

## Goal

Implement the MVP Dockerized AI code review server: MCP tools + Copilot SDK integration + Docker container. Code in, findings out.

## Scope

Everything in spec 001:
- MCP server exposing `start_review`, `discuss`, `get_review_summary`, `list_sessions` via stdio
- Copilot SDK integration with `list_models()` auto-selection
- SARIF-inspired finding model with stable IDs, fingerprints, evidence
- Content denylist validation (FR-006/FR-007)
- Deterministic bundle ordering (FR-008)
- Fail-fast on oversized bundles (FR-009)
- Idempotency tokens (FR-012), error classification (FR-013), timeout budgets (FR-014)
- Single Docker container, `docker compose up -d`
- Health check endpoint

## Out of Scope

- Credential setup UI (spec 002)
- Review dashboard (spec 003)
- Human oversight / approval (spec 004)
- Model configuration UI (spec 005)
- Fallback backends (spec 006)
- Eval harness (spec 007)

## Constraints

- Python 3.11+, FastAPI + uvicorn
- `mcp>=1.0.0` (Anthropic), `github-copilot-sdk>=0.1.0`
- TDD: red-green-refactor per constitution
- Advisory only: no CI status checks, no merge blocking
- Container has no host filesystem access
- `GITHUB_TOKEN` env var for MVP credentials

## Acceptance Criteria

- AC-1: `start_review` accepts a review bundle and returns SARIF-structured findings within 30s
- AC-2: `discuss` supports multi-turn rebuttal referencing findings by ID
- AC-3: `get_review_summary` returns finding counts by status, category, severity
- AC-4: `list_sessions` returns all sessions with metadata
- AC-5: Content denylist blocks `.env` and credential files before reaching Copilot
- AC-6: Duplicate calls with same idempotency token return same result
- AC-7: Findings maintain stable `finding_id` and `fingerprint` across rounds
- AC-8: `docker compose up -d` + `GITHUB_TOKEN` is all that's needed to start
- AC-9: Health check endpoint responds correctly

## Open Decisions

- Exact Python package structure (e.g., `server/` vs `src/server/`)
- Whether to use `asyncio` throughout or allow sync Copilot SDK calls
- Session storage: plain dict vs dataclass-based store
