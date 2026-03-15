# Agent-in-a-Box (AgentinaBox)

A Dockerized AI code review sidecar. It receives code via [MCP](https://modelcontextprotocol.io/) tool calls, forwards it to GitHub Copilot (via the Copilot SDK), and returns SARIF-structured findings.

**Project-agnostic** — it knows nothing about the repo it reviews until the orchestrating agent tells it.

## Architecture

```
Claude Code  ──MCP stdio──▶  Agent-in-a-Box container  ──SDK──▶  GitHub Copilot
                              (no host filesystem access)
```

- **MCP Server** exposes `start_review`, `discuss`, `get_review_summary`, `list_sessions` tools
- **Security boundary**: container has NO filesystem access to the host repo — all context arrives via MCP parameters
- **Single credential**: a fine-grained GitHub PAT with `copilot_requests` permission

## Quick Start

### Prerequisites

- Docker & Docker Compose
- A GitHub PAT (`github_pat_*`) with `copilot_requests` permission

### Run

```bash
export GITHUB_TOKEN=github_pat_...
docker compose up -d
```

The review server starts on `localhost:8080` with a `/health` endpoint.

### Connect from Claude Code

Add to your MCP config:

```json
{
  "mcpServers": {
    "code-reviewer": {
      "command": "docker",
      "args": ["exec", "-i", "<container-name>", "python", "-m", "server.mcp_server"]
    }
  }
}
```

> Replace `<container-name>` with the actual name (`docker compose ps --format '{{.Name}}'`). Default: `agent-in-a-box-review-server-1`.

## MCP Tools

| Tool | Description |
|------|-------------|
| `start_review` | Submit a code review bundle (diff, files, conventions) and receive structured findings |
| `discuss` | Follow up on a review session with questions or additional context |
| `get_review_summary` | Get summary statistics for a review session |
| `list_sessions` | List all active and resolved review sessions |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web framework | FastAPI + uvicorn |
| MCP SDK | `mcp` (Anthropic FastMCP) |
| Inner model | GitHub Copilot SDK (Technical Preview) |
| Templates | Jinja2 (server-rendered) |
| Testing | pytest |
| Container | Docker Compose |

## Development

```bash
# Create venv and install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest
pytest -x              # stop on first failure
pytest --cov=server    # with coverage

# Build container
docker compose build
docker compose up -d
```

## Design Principles

1. **Project-agnostic**: no hardcoded repo knowledge — all context via MCP
2. **No volume mounts**: container never sees the host filesystem
3. **Security boundary**: content denylist blocks `.env`, `*.pem`, `*.key`, credentials
4. **Model-agnostic**: MCP interface stays the same regardless of inner model
5. **YAGNI**: server-rendered UI, in-memory storage, no premature abstractions

## Roadmap

| Spec | Feature | Status |
|------|---------|--------|
| 001 | Core Review Server | Implemented |
| 002 | Credential Setup (PAT encryption) | Draft |
| 003 | Review Dashboard (web UI) | Draft |
| 004 | Human Oversight (approval workflow) | Draft |
| 005 | Model Configuration | Draft |
| 006 | Fallback Backends (OpenAI, Anthropic, etc.) | Draft |
| 007 | Eval Harness | Draft |

## License

See [LICENSE](LICENSE) for details.
