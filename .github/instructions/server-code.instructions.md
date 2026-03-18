---
applyTo: "server/**/*.py"
---

# Server Code Conventions

## Finding Parser Trust Model

The parser (`server/finding_parser.py`) uses a strict trust hierarchy for JSON extraction:

1. **Code-fenced JSON** (```` ```json ... ``` ````) — only `json`-tagged or plain (untagged) fences. Never match language-tagged fences like ```` ```python ````.
2. **Sentinel-delimited** (`BEGIN_FINDINGS_JSON ... END_FINDINGS_JSON`)
3. **Whole-response JSON** — only if entire stripped text is valid JSON

Bare JSON embedded in prose is the **ambiguous zone** and must NOT be extracted. This prevents fabricating findings from illustrative examples.

When unwrapping JSON objects, prefer well-known wrapper keys (`findings`, `results`, `items`, `issues`, `data`) before falling back to heuristics. Reject objects with multiple ambiguous list fields.

## Prompt Architecture

- `REVIEWER_PERSONA` — system prompt for initial reviews. Rule 5 ("no prose") is scoped to "initial review response" only.
- `FORMAT_REINFORCEMENT` — appended at end of user message for format compliance (sandwich technique).
- `DISCUSS_REINFORCEMENT` — appended after user follow-up message. Requests dual-format: conversational text first, then JSON findings in a code fence. This intentionally differs from REVIEWER_PERSONA's JSON-only rule.

Do not introduce conflicting format instructions between system prompt and reinforcement constants.

## Security Boundary

- The content denylist (`server/denylist.py`) must check BOTH `files` and `test_files` in ReviewBundle.
- Denylist patterns: `.env`, `*.pem`, `*.key`, `*credentials*`, `*secret*`, `*.p12`, `*.pfx`.
- `ContentDeniedError.denied_files` must be an actual `list[str]`, never a stringified repr.
- No secrets or credentials should be logged, stored, or returned in error messages beyond file paths.

## Pydantic Models

- All models use Pydantic v2 (`BaseModel` from `pydantic`).
- Enums use `(str, Enum)` pattern for JSON serialization.
- Use `from __future__ import annotations` in all modules.
- Severity levels: `BUG`, `WARN`, `NIT` (three-tier taxonomy).
- Categories: `correctness`, `design`, `tests`, `maintainability`, `security`, `style`.

## Error Types

- `ContentDeniedError(ValueError)` — denylist violation
- `BundleTooLargeError(ValueError)` — context exceeds model limit
- `CopilotTimeoutError` — retryable
- `CopilotAuthError` — terminal, do not retry
