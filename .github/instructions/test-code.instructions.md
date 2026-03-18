---
applyTo: "tests/**/*.py"
---

# Test Code Conventions

## General Patterns

- All tests use `pytest` with async support (no `unittest.TestCase`).
- Test classes group related tests: `class TestFeatureName:` with `async def test_specific_case(self, ...)`.
- Fixtures are defined in `tests/conftest.py` — prefer shared fixtures over inline setup.
- Mock the `CopilotReviewClient` using `AsyncMock` for `send_review` and `send_followup`.

## Assertion Quality

- When using `str.find()` for position checks, always assert the result is not `-1` before comparing positions. A `-1` return silently passes ordering assertions.
- Prefer specific assertions over generic ones: `assert result.model == "gpt-4o"` over `assert result.model`.
- Include descriptive failure messages for non-obvious assertions.
- When checking collections, assert both membership and count where applicable.

## Mock Conventions

- `mock_copilot_client` fixture returns an `AsyncMock` with `send_review` returning valid JSON findings and `selected_model = "gpt-4o"`.
- Prompt extraction from mock calls uses: `call_kwargs.kwargs.get("key") or call_kwargs.args[N]` — this is the established pattern, keep it consistent.
- When testing parser behavior, construct response strings directly rather than mocking the parser.

## Key Test Fixtures

- `sample_review_bundle` — minimal valid ReviewBundle with diff, files, test_files, spec, conventions
- `sample_bundle_with_denied_files` — bundle containing `.env` for denylist testing
- `mixed_output_response` — Copilot response with prose + JSON for dual-format testing
- `object_wrapped_response` — JSON wrapped in `{"findings": [...]}` object

## What to Test

- Happy path + edge cases (empty findings, zero-length diff, oversized bundle)
- Security boundaries (denylist on files AND test_files, denied file list type)
- Idempotency (duplicate tokens return cached results, cross-operation conflicts)
- Finding stability (IDs and fingerprints preserved across discuss rounds)
- Prompt ordering (FR-008 section order, reinforcement placement)
