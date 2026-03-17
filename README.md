# Agent-in-a-Box (AgentinaBox)

A Dockerized AI code review sidecar. It receives code via [MCP](https://modelcontextprotocol.io/) tool calls, forwards it to GitHub Copilot (via the Copilot SDK), and returns SARIF-structured findings.

**Project-agnostic** — it knows nothing about the repo it reviews until the orchestrating agent tells it.

## Why Agent-in-a-Box?

AI code review is increasingly commoditized — Claude Code, Codex CLI, and Copilot CLI all do it natively. Agent-in-a-Box is different because it's not a code review tool. It's a **containerized, MCP-speaking agent worker** designed to be composed into larger systems.

### Composable Agent Microservice

CI pipelines, Slack bots, and internal platforms don't want to manage Claude Code installations on every machine. They want to throw a payload at a container and get structured output back. Agent-in-a-Box exposes a clean MCP interface — send code in, get SARIF findings out. No setup on the host, no dependencies, no state.

### Enterprise Security by Design

The container has **zero filesystem access** to the host. All code arrives via MCP parameters. A content denylist blocks `.env`, `*.pem`, `*.key`, and credential files. The only secret in the container is a single API token. An enterprise security team can audit one container image and approve it — compare that to installing AI tools on every developer's machine and trusting their local configurations.

### Model-Agnostic Interface

The MCP contract stays the same whether Copilot, Claude, OpenAI, or a local Ollama model runs inside. The consuming system doesn't care what model answers — it sends code, it gets structured findings. Swap backends with a config change, not a code change.

### Scalable by Default

Spin up 50 containers, throw 50 PRs at them in parallel, tear them down. Stateless by design, horizontally scalable. This is the pattern that enterprises building internal AI platforms actually need — not a desktop tool, but a fleet of agent workers.

## Architecture

```text
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
| 006 | Fallback Backends (OpenAI, Anthropic, Gemini, Ollama) | Draft |
| 007 | Eval Harness | Draft |
| 008 | Prompt Tuning for Structured Output | In Progress |
| 009 | Slack Integration | Backlog |
| 010 | Agent SDK Backends (Claude Agent SDK, Codex CLI) | Backlog |
| 011 | REST API Transport (CI/CD integration) | Backlog |

## License

See [LICENSE](LICENSE) for details.
