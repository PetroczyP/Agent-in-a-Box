---
description: Show current state of a builder/judge task — round, phase, verdict, and latest findings summary.
---

## User Input

```text
$ARGUMENTS
```

## Instructions

### 1. Find the task

- If `$ARGUMENTS` contains a task ID (e.g., `001-ai-code-reviewer`), use `agent-loop/$ARGUMENTS/`
- If empty, scan all `agent-loop/*/status.json` files and show a summary of all tasks

### 2. Read and report

For each task, read `status.json` and report in a concise table:

| Field | Value |
|-------|-------|
| Task | task_id |
| Phase | phase |
| State | state |
| Round | round / max_rounds |
| Verdict | verdict or "pending" |
| Last updated | updated_at |

### 3. If a single task was requested

Also read the latest round from `judge.md` (if it exists) and summarize:
- Verdict
- Number of blockers / high / medium / low findings
- Any open questions

Keep the output short — this is a status check, not a full review.
