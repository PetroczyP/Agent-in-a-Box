# MCP Transport Contract: Eval Harness (007)

## Overview

The eval harness acts as an MCP **client** that connects to the AgentinaBox reviewer MCP **server** via stdio transport. This is the same transport Claude Code uses in production.

## Connection

```
Host (eval harness)                    Docker container (reviewer)
┌──────────────┐     docker exec -i    ┌──────────────────────┐
│ stdio_client │ ──── stdin/stdout ───→ │ python -m server.    │
│ ClientSession│ ←─── stdin/stdout ──── │        mcp_server    │
└──────────────┘                        └──────────────────────┘
```

**Protocol**: MCP over JSON-RPC 2.0 via stdio
**SDK**: `mcp.client.stdio.stdio_client` + `mcp.client.session.ClientSession`

## Connection Lifecycle

```python
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def connect(container: str) -> AsyncContextManager:
    """Create an MCP client session to the reviewer container."""
    server_params = StdioServerParameters(
        command="docker",
        args=["exec", "-i", container, "python", "-m", "server.mcp_server"],
    )
    # One session per eval run — reused across all cases
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
```

**Important**: A single MCP session is used for the entire eval run. Each golden case creates a new review session (via `start_review`), but all cases share the same MCP connection. This mirrors how Claude Code uses a long-lived MCP process for multiple reviews.

## Tool Calls

The eval harness uses these MCP tools (defined in `server/mcp_server.py`):

### start_review

Sends a golden case bundle to the reviewer.

```python
result = await session.call_tool("start_review", arguments={
    "diff": case.bundle.diff,
    "files": case.bundle.files,
    "test_files": case.bundle.test_files,
    "conventions": case.bundle.conventions,
    "context": case.bundle.context,
    "branch": f"eval-{case.case_id}",
})
# result.content contains the ReviewResult JSON
```

**Input**: `ReviewBundle` fields as a dict (matching `server/models.py:ReviewBundle`)
**Output**: `ReviewResult` JSON with `session_id`, `model`, `findings`, `finding_count`, `severity_summary`

### discuss (multi-turn cases only)

Sends a scripted rebuttal message. **Before calling discuss**, the runner must resolve the stable `target_expected_id` from the turn script into the actual runtime `finding_id` assigned by the reviewer in this trial.

#### Finding ID Resolution

After `start_review`, the runner executes the **full grading pipeline** (Tier 1 fingerprint matching, then Tier 2 semantic grading for unmatched findings per FR-018) on all findings returned by the reviewer. This produces `GraderResult` objects, some of which have `matched_expected_id` set. The runner uses the complete grading results to resolve rebuttal targets:

1. Look up `turn.target_expected_id` in the grading results
2. Find any `GraderResult` where `matched_expected_id == turn.target_expected_id` AND `verdict` is `match` or `partial_match` (from either Tier 1 or Tier 2)
3. Use that `GraderResult.actual_finding_id` as the resolved finding ID
4. Substitute it into `turn.rebuttal_message_template` (replacing `{finding_id}`)

This ensures that findings matched semantically by Tier 2 (e.g., the reviewer found the right issue with different wording or a shifted location that didn't meet fingerprint tolerance) are still eligible for scripted rebuttals.

If the target expected finding was not matched by **either tier** in this trial, the turn is **skipped** and recorded as `finding_not_found` in `RebuttalResult`.

#### Tool Call

```python
# Resolve finding_id from grading results
resolved_id = resolve_finding_id(grader_results, turn.target_expected_id)
if resolved_id is None:
    # Skip turn — expected finding not matched in this trial
    record_rebuttal_result(turn, finding_not_found=True)
    continue

message = turn.rebuttal_message_template.format(finding_id=resolved_id)
result = await session.call_tool("discuss", arguments={
    "session_id": review_session_id,
    "message": message,
})
# result.content contains the DiscussResult JSON
```

**Input**: `DiscussRequest` fields (`session_id`, `message`)
**Output**: `DiscussResult` JSON with `response`, `updated_findings`, `finding_count_by_status`

### get_review_summary (multi-turn cases only)

Gets final finding statuses after discussion.

```python
result = await session.call_tool("get_review_summary", arguments={
    "session_id": review_session_id,
})
# result.content contains the ReviewSummary JSON
```

**Input**: `SummaryRequest` fields (`session_id`)
**Output**: `ReviewSummary` JSON with final `findings` and status breakdowns

## Error Handling

| MCP Error | Eval Behavior |
|-----------|---------------|
| Tool returns `{"error": "rate_limited", ...}` | Retry with exponential backoff (FR-013) |
| Tool returns `{"error": "timeout", ...}` | Retry with exponential backoff (FR-013) |
| Tool returns `{"error": "auth_failed", ...}` | Abort run — non-retryable |
| Tool returns `{"error": "unavailable", ...}` | Abort run — non-retryable |
| Connection lost (process died) | Abort run — container may need restart |
| Tool returns `{"error": "content_denied", ...}` | Log and skip case — golden case has denylist violation (fixture error) |

## Result Parsing

MCP `call_tool` returns `CallToolResult` with a `content` list. The eval harness:
1. Extracts the first `TextContent` item from `result.content`
2. Parses the text as JSON
3. Validates against the expected Pydantic model (`ReviewResult`, `DiscussResult`, `ReviewSummary`)
4. On parse failure: logs the raw response and marks the trial as `error`
