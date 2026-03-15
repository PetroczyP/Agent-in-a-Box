# Quick Reference: What to Type

## Claude Code (builder)

| What you want | What you type |
|--------------|---------------|
| Start a brand new feature | `/loop.build new <one-line description>` |
| Continue working on a task | `/loop.build <task-id>` or just `/loop.build` (auto-detects) |
| Advance to next phase | `/loop.build <task-id> <phase>` (e.g., `/loop.build 001 plan`) |
| Check status of all tasks | `/loop.status` |
| Check status of one task | `/loop.status <task-id>` |

## Codex (judge)

| What you want | What you type |
|--------------|---------------|
| Review the builder's output | `judge <task-id>` (e.g., `judge 001-core-review-server`) |

Codex reads `CODEX.md` at the project root, which contains the full judge workflow.

## Typical session

```
Peter → Claude:   /loop.build new Dockerized AI code review server
Peter → Codex:    judge 001-core-review-server
Peter → Claude:   /loop.build 001-core-review-server
Peter → Codex:    judge 001-core-review-server
  ... repeat until accepted ...
Peter → Claude:   /loop.build 001-core-review-server design
Peter → Codex:    judge 001-core-review-server
  ... repeat until accepted ...
Peter → Claude:   /loop.build 001-core-review-server plan
  ... and so on through build → test → release ...
```

You never explain context. Everything is in the shared files.
