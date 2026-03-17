# Implementation Plan: Prompt Tuning for Structured Copilot Output

**Branch**: `008-prompt-tuning` | **Date**: 2026-03-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-prompt-tuning/spec.md`

## Summary

Tune the reviewer persona prompt and harden the finding parser so GitHub Copilot returns structured JSON findings instead of conversational text. Three complementary techniques: (1) few-shot format examples in the system prompt, (2) format reinforcement suffix after review context, (3) lenient JSON parsing for mixed/truncated output. Includes iteration loops for empirical prompt testing against live Copilot.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `json-repair` (new, for FR-007), existing: `mcp>=1.0.0`, `github-copilot-sdk>=0.1.0`, `pydantic>=2.12`
**Storage**: N/A (no new storage — modifies in-memory prompt strings and parser logic)
**Testing**: pytest (existing suite of 154+ tests, add ~20-30 new tests for parser hardening and prompt validation)
**Target Platform**: Docker container (`python:3.11-slim-bookworm` + Node.js 22)
**Project Type**: Library enhancement (modifying 3 existing files + adding dependency)
**Performance Goals**: Minimal local overhead — changes are to prompt strings and parser logic, not I/O paths. Prompt size increase (few-shot examples + reinforcement suffix) is small relative to 128K context budget but increases request payload to Copilot, which may affect model-side latency and cost. Actual impact measured during build-phase iteration (D-5).
**Constraints**: System prompt (REVIEWER_PERSONA) must stay under ~12,800 chars (10% of 128K context budget per SC-005)
**Scale/Scope**: 3 source files modified (`server/prompts.py`, `server/finding_parser.py`, `server/review_engine.py`), 2 dependency files updated (`requirements.txt` + `pyproject.toml`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Project-Agnostic | PASS | Prompt examples are generic code review patterns, not project-specific |
| II. Context via MCP | PASS | No filesystem access changes. Context still arrives via MCP tool calls |
| III. Security Boundary | PASS | No secrets in prompts. Content denylist unchanged |
| IV. Test-First | PASS | TDD for parser changes. Live validation for prompt changes (iteration loops) |
| V. Model-Agnostic | PASS | Prompt works with any Copilot model. No model ID hardcoding |
| VI. YAGNI | PASS | `json-repair` justified by FR-007. No prompt framework — direct constants. No new MCP params |

**New dependency justification**: `json-repair` is a focused, zero-dependency library for repairing LLM-generated JSON. Rolling our own repair logic would be more code, less reliable, and harder to maintain. The alternative (simple bracket closing) fails for real-world truncation patterns.

## Project Structure

### Documentation (this feature)

```text
specs/008-prompt-tuning/
├── spec.md              # Feature specification (accepted)
├── plan.md              # This file
├── research.md          # Decisions 1-6
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Generated during plan phase
```

### Source Code (files modified)

```text
server/
├── prompts.py           # REVIEWER_PERSONA (enhanced), FORMAT_REINFORCEMENT (new),
│                        # DISCUSS_REINFORCEMENT (new), build_review_context (modified)
├── finding_parser.py    # _try_json (hardened), _try_json_repair (new), _try_object_unwrap (new)
└── review_engine.py     # discuss() prompt assembly (format reinforcement added)

tests/
├── test_finding_parser.py  # New tests: mixed output, object unwrap, truncated JSON, fallback regression
├── test_prompts.py         # New tests: prompt size, format reinforcement presence
└── conftest.py             # Updated fixtures for new parser test scenarios

requirements.txt            # Add json-repair (Docker install path)
pyproject.toml              # Add json-repair to [project] dependencies (CI + editable install path)
```

### Contracts

No new contracts needed. The MCP interface (`start_review`, `discuss`, `get_review_summary`, `list_sessions`) is unchanged. The `FindingParser` interface is internal and its contract is defined by the existing test suite + FR-009 fallback preservation.

The key interface change is in `build_review_context()`:
- **Before**: Returns assembled context string
- **After**: Accepts optional `reinforce_format: bool = True` parameter; appends `FORMAT_REINFORCEMENT` suffix when True

The `discuss()` method in `review_engine.py` will append `DISCUSS_REINFORCEMENT` after the follow-up prompt (user message + any additional files). This is consistent with D-6: format reinforcement placed last maximizes compliance. This is internal — no MCP contract change.

## Complexity Tracking

No constitution violations to justify.
