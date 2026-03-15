# MCP Tool Contracts: Core Review Server (001)

## Transport

stdio via `docker exec -i <container> python -m server.mcp_server`

## Tool: `start_review`

Starts a new code review session. Validates the bundle against the content denylist, orders context deterministically, and forwards to Copilot.

### Input

```python
class ReviewBundle(BaseModel):
    diff: str                              # git diff content
    files: dict[str, str]                  # {path: content} for changed files
    test_files: dict[str, str] | None      # {path: content} for test files
    spec: str | None                       # spec/task artifacts
    conventions: str | None                # project rules (CLAUDE.md, etc.)
    anti_patterns: str | None              # known anti-patterns
    test_results: str | None               # test runner output
    context: str | None                    # free-form context (PR desc, issue title)
    branch: str | None                     # branch name for session metadata
    model: str | None                      # model override (optional)
    idempotency_token: str | None          # client-generated dedup token
```

### Output (success)

```python
class ReviewResult(BaseModel):
    session_id: str
    model: str                             # model actually used
    findings: list[Finding]
    finding_count: int
    severity_summary: dict[str, int]       # {"BUG": 1, "WARN": 2, "NIT": 0}
```

### Errors

| Condition | Error |
|-----------|-------|
| Denylist violation | `{"error": "content_denied", "denied_files": [...], "retryable": false}` |
| Bundle exceeds model context | `{"error": "bundle_too_large", "bundle_size": N, "model_limit": M, "guidance": "Reduce bundle by omitting test_results or limiting files to the most changed", "retryable": false}` |
| Empty diff | `{"error": "empty_diff", "retryable": false}` |
| Copilot auth failure | `{"error": "auth_failed", "message": "...", "retryable": false}` |
| Copilot model unavailable | `{"error": "unavailable", "message": "...", "retryable": false}` |
| Copilot timeout | `{"error": "timeout", "message": "...", "retryable": true}` |
| Copilot rate limit | `{"error": "rate_limited", "message": "...", "retryable": true}` |
| Idempotent duplicate | Returns original cached result (not an error) |
| Idempotency token conflict | `{"error": "idempotency_conflict", "message": "Token already used for a different request", "retryable": false}` |
| Unrecognized validation error | `{"error": "unknown", "message": "...", "retryable": false}` |
| Unexpected internal error | `{"error": "internal", "message": "...", "retryable": <bool>}` — retryable reflects the original exception's own flag (defaults to `false`) |

---

## Tool: `discuss`

Sends a follow-up message in an active review session. Supports rebuttals, additional file attachments, and multi-turn discussion.

### Input

```python
class DiscussRequest(BaseModel):
    session_id: str
    message: str                           # rebuttal, question, or context
    additional_files: dict[str, str] | None # {path: content} new files
    idempotency_token: str | None
```

### Output (success)

```python
class DiscussResult(BaseModel):
    response: str                          # Copilot's response text
    updated_findings: list[Finding]        # findings with updated statuses
    finding_count_by_status: dict[str, int] # {"open": 1, "dismissed": 1, "fixed": 1}
```

### Errors

| Condition | Error |
|-----------|-------|
| Session not found | `{"error": "session_not_found", "retryable": false}` |
| Session not active | `{"error": "session_not_active", "retryable": false}` |
| Denylist violation in attached files | `{"error": "content_denied", "denied_files": [...], "retryable": false}` |
| Copilot auth failure | `{"error": "auth_failed", "message": "...", "retryable": false}` |
| Copilot model unavailable | `{"error": "unavailable", "message": "...", "retryable": false}` |
| Copilot timeout | `{"error": "timeout", "message": "...", "retryable": true}` |
| Copilot rate limit | `{"error": "rate_limited", "message": "...", "retryable": true}` |
| Idempotent duplicate | Returns original cached result (not an error) |
| Idempotency token conflict | `{"error": "idempotency_conflict", "message": "Token already used for a different request", "retryable": false}` |
| Unrecognized validation error | `{"error": "unknown", "message": "...", "retryable": false}` |
| Unexpected internal error | `{"error": "internal", "message": "...", "retryable": <bool>}` — retryable reflects the original exception's own flag (defaults to `false`) |

---

## Tool: `get_review_summary`

Returns a summary of a review session's findings.

### Input

```python
class SummaryRequest(BaseModel):
    session_id: str
```

### Output (success)

```python
class ReviewSummary(BaseModel):
    session_id: str
    status: str                            # "active" or "resolved"
    model: str
    round_count: int                       # number of discuss rounds
    findings: list[Finding]
    finding_count: int
    by_severity: dict[str, int]            # {"BUG": 1, "WARN": 2, "NIT": 0}
    by_category: dict[str, int]            # {"correctness": 1, "style": 2}
    by_status: dict[str, int]              # {"open": 1, "dismissed": 1, "fixed": 1}
```

### Errors

| Condition | Error |
|-----------|-------|
| Session not found | `{"error": "session_not_found", "retryable": false}` |
| Unrecognized validation error | `{"error": "unknown", "message": "...", "retryable": false}` |

---

## Tool: `list_sessions`

Returns all review sessions with metadata.

### Input

None (no parameters)

### Output (success)

```python
class SessionList(BaseModel):
    sessions: list[SessionInfo]

class SessionInfo(BaseModel):
    session_id: str
    branch: str | None
    status: str
    model: str
    round_count: int
    finding_count: int
    by_severity: dict[str, int]            # {"BUG": 1, "WARN": 2, "NIT": 0}
    by_category: dict[str, int]            # {"correctness": 1, "style": 2}
    created_at: str                        # ISO 8601
    updated_at: str                        # ISO 8601
```
