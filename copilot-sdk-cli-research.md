# Copilot SDK + Claude Code: Cross-Agent Code Review

## Research Date: 2026-03-12

> **Review status:** Copilot-reviewed twice (2026-03-12/13). Round 1: 8 errors fixed
> (package names, imports, API pattern, auth, pricing). Round 2: 5 errors fixed
> (event types, `session.on()` syntax, `--headless` flag, added `send_and_wait()`,
> section numbering). Added `customAgents`, `github_token` param, correct imports.
> **Round 3 (2026-03-13):** Cross-validated by Claude Code + Codex. 12 fixes:
> classic PATs → fine-grained PATs, `--headless` → `--acp`, Node 20 → 22,
> retired models (GPT-5, o3) replaced, `systemMessage` → `system_message`,
> `delta_content` → `content`, `define_tool` import fixed, .NET SDK added,
> Business tier added, `copilot` scope → `copilot_requests` permission,
> macOS ARM64 open question resolved.

## Goal

Explore whether a Copilot SDK-based agent running locally (Docker on macOS) can be
called by Claude Code for interactive, multi-turn code review discussions.

---

## 1. Prerequisites

### 1.1 Copilot CLI (required by the SDK)

The Copilot SDK manages a Copilot CLI process in "server mode" under the hood.
You need the standalone CLI installed:

```bash
# Install the standalone Copilot CLI (GA since Feb 25, 2026)
npm install -g @github/copilot

# Verify installation
copilot --version

# Authenticate — use one of these methods:
# Option A: Interactive (run copilot, then type /login inside the CLI)
copilot
# > /login

# Option B: Environment variable (for scripts / Docker)
# IMPORTANT: Classic PATs (github_pat_) are NOT supported by Copilot CLI.
# Use a fine-grained PAT (github_pat_) with "Copilot Requests" permission.
export GITHUB_TOKEN=github_pat_your_fine_grained_token
```

> **Important:** The old `gh copilot` extension was announced deprecated Sept 25,
> 2025 and ceased functioning Oct 25, 2025. The new standalone `copilot` CLI is a
> separate binary installed via npm.

> **Auth token types supported by Copilot CLI:**
>
> | Token type | Prefix | Supported |
> | ---------- | ------ | --------- |
> | Fine-grained PAT (with `copilot_requests` permission) | `github_pat_` | Yes |
> | OAuth device-flow token | `gho_` | Yes |
> | GitHub App user-to-server token | `ghu_` | Yes |
> | Classic PAT | `github_pat_` | **Not supported** |

### 1.2 Copilot SDK (Technical Preview)

```bash
# Python SDK (PyPI name differs from import name)
pip install github-copilot-sdk    # import as: from copilot import CopilotClient

# Node.js SDK
npm install @github/copilot-sdk

# Go SDK (subdirectory of the main repo, not a separate repo)
go get github.com/github/copilot-sdk/go

# .NET SDK
dotnet add package GitHub.Copilot.SDK
```

The SDK starts the CLI in JSON-RPC server mode automatically, or you can point it
at an already-running server process.

### 1.3 Copilot Subscription

A GitHub Copilot plan is required:

- Copilot Free — limited usage (SDK FAQ confirms free tier for non-BYOK)
- Copilot Pro ($10/mo) — higher rate limits
- Copilot Pro+ ($39/mo) — includes the coding agent
- Copilot Business ($19/user/mo) — org-level management
- Copilot Enterprise ($39/user/mo) — org-level with knowledge bases

> **Note:** GitHub's own pages are inconsistent on CLI availability per tier.
> The Feb 25 2026 GA announcement says "paid subscribers"; current docs say
> "all Copilot plans." Verify against current docs before relying on free-tier access.

---

## 2. Architecture: Path 3 — Custom MCP Review Server

### 2.1 High-Level Flow

```
                        MCP (stdio or HTTP+SSE)
┌──────────────┐       ┌─────────────────────────────────────────────┐
│              │       │          Review Server (Docker)              │
│  Claude Code │◄─────►│                                             │
│  (Opus 4.6)  │  tools│  FastAPI app on :8080                       │
│              │       │                                             │
│  Orchestrator│       │  ┌───────────┐    ┌──────────────────────┐  │
│  & primary   │       │  │ MCP Server│    │ Web UI (localhost)   │  │
│  code author │       │  │ endpoint  │    │ - Live transcript    │  │
│              │       │  └─────┬─────┘    │ - Approve/reject     │  │
│              │       │        │           │ - Conversation log   │  │
└──────────────┘       │        ▼           └──────────────────────┘  │
                       │  ┌───────────┐                               │
                       │  │ Review    │                               │
                       │  │ Engine    │                               │
                       │  │           │                               │
                       │  │ Manages   │                               │
                       │  │ sessions, │                               │
                       │  │ formats   │                               │
                       │  │ prompts   │                               │
                       │  └─────┬─────┘                               │
                       │        │                                     │
                       │        ▼                                     │
                       │  ┌───────────┐                               │
                       │  │ Copilot   │                               │
                       │  │ SDK       │                               │
                       │  │ (Python)  │──► copilot CLI (server mode)  │
                       │  └───────────┘         (JSON-RPC)            │
                       └─────────────────────────────────────────────┘
```

### 2.2 What Claude Code Sees (MCP Tools)

The review server exposes itself as an MCP server with these tools:

```
┌─────────────────────────────────────────────────────────────┐
│ MCP Tools exposed to Claude Code                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ start_review(                                                    │
│   diff,              — git diff main...HEAD                      │
│   files,             — { path: content } for every changed file  │
│   test_files,        — { path: content } for related tests       │
│   spec,              — spec.md + tasks.md concatenated           │
│   conventions,       — CLAUDE.md rules section                   │
│   anti_patterns,     — .claude/anti-patterns.md                  │
│   test_results,      — test runner stdout/stderr                 │
│   context            — issue title, PR description, etc.         │
│ )                                                                │
│   → Creates review session, sends full bundle to Copilot         │
│   → Returns: session_id + initial review findings                │
│                                                                  │
│ discuss(session_id, message, additional_files?)                   │
│   → Multi-turn: Claude sends response/question/rebuttal          │
│   → Can attach extra files on demand (if reviewer asks)          │
│   → Returns: Copilot's response                                  │
│                                                                  │
│ get_review_summary(session_id)                                   │
│   → Returns: final findings, resolved/dismissed, stats           │
│                                                                  │
│ list_sessions()                                                  │
│   → Returns: active review sessions with status                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Interaction Flow (Typical Code Review)

```
Step  Actor          Action
───── ────────────── ──────────────────────────────────────────────
1     Claude Code    Finishes implementation, runs tests
2     Claude Code    Calls start_review(diff=<git diff>, context=<PR description>)
3     Review Server  Sends diff + review prompt to Copilot SDK
4     Copilot        Returns initial findings (e.g., 3 issues found)
5     Review Server  Returns findings to Claude Code via MCP
6     Claude Code    Reads findings, disagrees with #2, calls discuss()
7     Copilot        Responds: "You're right about #2, but #1 and #3 stand"
8     Claude Code    Fixes #1 and #3, calls discuss() with updated diff
9     Copilot        Confirms fixes look good, no new issues
10    Claude Code    Calls get_review_summary() → clean report
11    Human          Reviews transcript on localhost:8080 web UI
```

### 2.4 What You See on localhost:8080

```
┌─────────────────────────────────────────────────────────┐
│  Code Review Dashboard                    localhost:8080 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Session: review-abc123    Status: Active    Round: 3   │
│  Branch: feature/issue-198                              │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ [Copilot] Initial review:                       │    │
│  │  1. WARN: Missing error boundary in VideoSec... │    │
│  │  2. INFO: Consider memoizing the callback...    │    │
│  │  3. BUG:  Race condition in useEffect cleanup   │    │
│  ├─────────────────────────────────────────────────┤    │
│  │ [Claude]  Re: #2 — This callback is only used   │    │
│  │  in the render closure, memoization would add   │    │
│  │  complexity without measurable benefit. The     │    │
│  │  component re-renders only on language change.  │    │
│  ├─────────────────────────────────────────────────┤    │
│  │ [Copilot] Fair point on #2 — dismissed.         │    │
│  │  #1 and #3 still stand. For #3, the cleanup     │    │
│  │  function should abort the fetch controller.    │    │
│  ├─────────────────────────────────────────────────┤    │
│  │ [Claude]  Fixed #1 (added ErrorBoundary) and    │    │
│  │  #3 (AbortController in useEffect). Updated     │    │
│  │  diff attached.                                 │    │
│  ├─────────────────────────────────────────────────┤    │
│  │ [Copilot] LGTM. No new issues found.            │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  [Approve & Close]  [Request Another Round]  [Export]   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Implementation Plan

### 3.1 Design Principle: Project-Agnostic

This container is **not** tied to explainIT or any specific codebase. It's a
generic "AI code reviewer" that:

- Receives all project context through MCP tool calls (the review bundle)
- Knows nothing about the repo it's reviewing until Claude tells it
- Can be shared as a Docker image on GitHub Container Registry (ghcr.io)
- Works with any AI coding agent that speaks MCP (Claude Code, Copilot CLI, etc.)

A colleague with Docker Desktop + a GitHub account with Copilot access can
run it out of the box.

### 3.2 Project Structure

```text
ai-code-reviewer/                    # Standalone repo (NOT inside explainIT)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── LICENSE
├── README.md                        # Setup guide for colleagues
│
├── server/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app + lifespan
│   ├── mcp_server.py                # MCP tool definitions (stdio or HTTP+SSE)
│   ├── review_engine.py             # Session management, prompt formatting
│   ├── copilot_client.py            # Copilot SDK wrapper
│   ├── models.py                    # Pydantic models (ReviewSession, Finding, etc.)
│   ├── secrets.py                   # First-run setup + credential storage
│   └── web_ui.py                    # Jinja2 templates for localhost dashboard
│
├── templates/
│   ├── dashboard.html               # Session list
│   ├── session.html                 # Transcript view
│   └── setup.html                   # First-run setup wizard
│
├── static/
│   └── style.css
│
├── tests/
│   ├── test_review_engine.py
│   └── test_mcp_tools.py
│
└── docs/
    └── mcp-integration.md           # How to connect from Claude Code / other agents
```

### 3.3 Key Dependencies

```text
# requirements.txt
fastapi>=0.128.0
uvicorn>=0.30.0
github-copilot-sdk>=0.1.0    # GitHub Copilot SDK (Technical Preview, import as `copilot`)
mcp>=1.0.0                    # MCP Python SDK (for server implementation)
pydantic>=2.12.0
jinja2>=3.1.0
cryptography>=44.0.0          # For encrypting stored credentials at rest
```

### 3.4 Secret Handling and First-Run Setup

#### What secrets are needed

Only **one credential** is required:

| Secret | What it is | How to get it |
| ------ | ---------- | ------------- |
| `GITHUB_TOKEN` | GitHub fine-grained Personal Access Token | github.com → Settings → Developer settings → Personal access tokens → Fine-grained tokens |

The token needs this permission:

- `copilot_requests` (write) — enables making Copilot API requests
- No repo access needed — the container never touches git or GitHub repos

> **Important:** Classic PATs (`ghp_`) are **not supported** by Copilot CLI/SDK.
> Use a fine-grained PAT (`github_pat_`) with the "Copilot Requests" permission.

> **Why not OAuth device flow?** Device flow requires a browser interaction
> inside the container, which is awkward in headless Docker. A PAT is simpler,
> portable, and works in CI too. The trade-off is token rotation is manual.

#### First-run setup flow

When the container starts for the first time (no credentials stored), the
web UI at `localhost:8080` shows a setup page instead of the dashboard:

```text
┌─────────────────────────────────────────────────────────────────────┐
│  AI Code Reviewer — First-Time Setup                localhost:8080  │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                     │
│  Welcome! This tool needs a GitHub token to call the Copilot API.  │
│                                                                     │
│  Step 1: Create a GitHub Fine-Grained Personal Access Token        │
│                                                                     │
│    Go to: github.com/settings/tokens?type=beta                     │
│    Required permission: Copilot Requests (write)                    │
│                                                                     │
│    Don't have Copilot? You need one of:                            │
│    • Copilot Free (limited usage)                                  │
│    • Copilot Pro ($10/mo)                                          │
│    • Copilot Pro+ ($39/mo)                                         │
│    • Copilot Enterprise (via org)                                  │
│                                                                     │
│  Step 2: Paste your token                                          │
│                                                                     │
│    ┌──────────────────────────────────────────────────────────┐     │
│    │ github_pat_••••••••••••••••••••••••••••••••••••            │     │
│    └──────────────────────────────────────────────────────────┘     │
│                                                                     │
│  Step 3: Verify                                                    │
│                                                                     │
│    [ Save & Test Connection ]                                      │
│                                                                     │
│  ─────────────────────────────────────────────────────────────────  │
│  Your token is encrypted at rest and stored in a Docker volume.    │
│  It never leaves this container. You can rotate it anytime from    │
│  the Settings page.                                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

After clicking "Save & Test Connection", the server:

1. Validates the token against the GitHub API (`GET /user` + verify `copilot_requests` permission)
2. Encrypts it with a Fernet key derived from a container-local secret
3. Stores the encrypted token in the Docker volume at `/data/credentials.enc`
4. Redirects to the main dashboard

#### Credential storage architecture

```text
┌──────────────────────────────────────────────────────┐
│ Docker container                                     │
│                                                      │
│   GITHUB_TOKEN (plaintext)                           │
│       ↓                                              │
│   Fernet.encrypt(token, key)                         │
│       ↓                                              │
│   /data/credentials.enc  ←── Docker named volume     │
│                               (persists across       │
│   /data/.key             ←──  container restarts)    │
│                                                      │
│   On startup:                                        │
│   1. Read /data/.key                                 │
│   2. Decrypt /data/credentials.enc                   │
│   3. Set GITHUB_TOKEN in process env                 │
│   4. Start Copilot SDK                               │
└──────────────────────────────────────────────────────┘
```

> **Security note:** The encryption key lives in the same volume as the encrypted
> token — this protects against casual inspection (`docker inspect`, accidental
> volume copy) but not against a determined attacker with root access to the host.
> This is the same security model as Docker secrets and `.docker/config.json`.
> For higher security, use Docker Swarm secrets or an external vault.

#### Three ways to provide credentials

| Method | For whom | How |
| ------ | -------- | --- |
| **Web UI setup** (recommended) | Colleagues with Docker Desktop | Open `localhost:8080`, paste token, done |
| **Environment variable** | CI pipelines, power users | `docker run -e GITHUB_TOKEN=github_pat_...` (fine-grained PAT only) |
| **Docker secret** | Swarm / production deployments | `docker secret create github_token token.txt` |

Priority: env var > Docker secret > stored credential. If `GITHUB_TOKEN` is set
in the environment, the container uses it directly and skips the stored credential.

### 3.5 Model Configuration

#### What models are available?

The Copilot SDK routes through the same model pool as GitHub Copilot Chat.
Which models you can use depends on your subscription:

| Tier | Available models (as of March 2026) |
| ---- | ----------------------------------- |
| **Copilot Free** | Claude Sonnet 4.5 (default), GPT-4o |
| **Copilot Pro** | + Claude Sonnet 4.6, GPT-4o |
| **Copilot Pro+** | + Claude Opus 4.6, GPT-5.2, GPT-5.4, Gemini 2.5 Pro |
| **Copilot Business** | Org-configured model list |
| **Copilot Enterprise** | Org-configured model list |

> **Warning:** Models are retired frequently. GPT-5 (retired 2026-02-17) and
> o3 (retired 2025-10-23) no longer work. **Always use `list_models()` at runtime**
> rather than hardcoding model IDs. The table above will go stale.

#### How the review server picks a model

Three levels, in priority order:

```text
1. Per-review override    →  start_review(..., model="claude-opus-4-6")
   (Claude Code passes it in the MCP tool call — for special cases)

2. Server config          →  Settings page on localhost:8080
   (user picks once, persisted in /data/config.json)

3. Default                →  Best available model from list_models()
   (auto-selects the most capable model the subscription allows)
```

#### Settings page (part of the web UI)

The setup wizard (Section 3.4) gets a second step after token validation:

```text
┌─────────────────────────────────────────────────────────────────────┐
│  AI Code Reviewer — Settings                        localhost:8080  │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                     │
│  GitHub Token    github_pat_••••••a3f7    [Change]                  │
│  Status          Connected                                         │
│                                                                     │
│  Review Model                                                      │
│                                                                     │
│    Available models (from your Copilot subscription):              │
│                                                                     │
│    ○ Claude Sonnet 4.6     (default — fast, good quality)          │
│    ● Claude Opus 4.6       (slower, best quality)       ← selected │
│    ○ GPT-5.4               (OpenAI flagship)                       │
│    ○ GPT-5.2               (OpenAI alternative)                    │
│    ○ Gemini 2.5 Pro        (Google flagship)                       │
│    ○ GPT-4o                (fast, cheaper)                         │
│                                                                     │
│    Models are fetched live from your subscription via              │
│    list_models(). If your plan changes, this list updates          │
│    automatically.                                                  │
│                                                                     │
│  [ Save ]                                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### How auto-select works (the default)

If no model is configured, the server calls `list_models()` on startup and
picks the most capable one using a hardcoded preference order:

```python
MODEL_PREFERENCE = [
    "claude-opus-4-6",       # Best reasoning, best for code review
    "gpt-5.4",               # Strong alternative (GPT-5 retired 2026-02-17)
    "gpt-5.2",               # Solid alternative
    "claude-sonnet-4-6",     # Good balance of speed and quality
    "claude-sonnet-4-5",     # Good fallback
    "gpt-4o",                # Fast fallback
]
# WARNING: Models get retired without much notice (e.g., GPT-5, o3).
# This list should be validated against list_models() on each release.

async def select_best_model(client: CopilotClient) -> str:
    available = await client.list_models()
    available_ids = {m.id for m in available}
    for model in MODEL_PREFERENCE:
        if model in available_ids:
            return model
    return available[0].id   # Fallback: first available
```

#### Per-review override from Claude Code

The `start_review` MCP tool accepts an optional `model` parameter:

```text
start_review(
  diff: "...",
  files: {...},
  ...
  model: "gpt-5.4"     # Optional — use a specific model for this review only
)
```

This lets Claude Code pick a different model for specific reviews (e.g., a
stronger model for complex changes) without changing the server's default.

#### Config persistence

```text
/data/config.json
{
  "model": "claude-opus-4-6",       // null = auto-select
  "model_preference": [...]          // optional custom preference order
}
```

Stored in the same Docker volume as credentials. Survives container restarts.

### 3.6 Docker Setup

```yaml
# docker-compose.yml
services:
  review-server:
    build: .
    ports:
      - "127.0.0.1:8080:8080"    # Web UI — localhost only, not exposed to network
    volumes:
      - reviewer-data:/data        # Persists credentials + session history
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN:-}   # Optional — if set, skips stored credential

volumes:
  reviewer-data:                   # Named volume — survives container rebuilds
```

```dockerfile
# Dockerfile
FROM python:3.11-slim-bookworm

# Node.js 22+ needed for Copilot CLI (Node 20 is NOT sufficient)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home appuser
WORKDIR /home/appuser/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Copilot CLI (required by the SDK)
RUN npm install -g @github/copilot

COPY server/ ./server/
COPY templates/ ./templates/
COPY static/ ./static/

RUN mkdir -p /data && chown appuser:appuser /data
USER appuser

EXPOSE 8080

# Health check for Docker Desktop visibility
HEALTHCHECK --interval=30s --timeout=5s \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### Colleague quick-start (what goes in the README)

```bash
# One command to start
docker compose up -d

# Open browser
open http://localhost:8080      # macOS
# First time: paste your GitHub token in the setup wizard
# After that: you see the review dashboard

# To connect from Claude Code (add to your ~/.claude.json or project .mcp.json)
claude mcp add code-reviewer -- docker exec -i ai-code-reviewer python -m server.mcp_server
```

### 3.7 Claude Code Integration

The MCP server runs inside the container. Claude Code talks to it via
`docker exec` (stdio transport) — no port mapping needed for MCP.

Add to **user-level** Claude config (`~/.claude.json`) so it works across all projects:

```json
{
  "mcpServers": {
    "code-reviewer": {
      "command": "docker",
      "args": ["exec", "-i", "ai-code-reviewer", "python", "-m", "server.mcp_server"]
    }
  }
}
```

Or per-project in `.mcp.json`:

```json
{
  "mcpServers": {
    "code-reviewer": {
      "command": "docker",
      "args": ["exec", "-i", "ai-code-reviewer", "python", "-m", "server.mcp_server"]
    }
  }
}
```

> **Why `docker exec` instead of HTTP?** MCP over stdio is Claude Code's native
> transport. No port conflicts, no CORS, no auth layer needed between Claude and
> the container. The web UI port (8080) is only for the human monitoring dashboard.

---

## 4. Copilot SDK Deep Dive

### 4.1 How the SDK Works

The SDK uses a **session + event** model, not a simple `chat()` request/response.

#### Simple path: `send_and_wait()` (recommended for the review engine)

```python
from copilot import CopilotClient

# The SDK accepts the token directly — no env var passthrough needed
client = CopilotClient(github_token="github_pat_...")
await client.start()

# Create a session with a custom reviewer persona
session = await client.create_session({
    "model": "gpt-5.4",
    "system_message": "You are a senior code reviewer. Classify findings as BUG/WARN/NIT.",
    # customAgents MAY work for a full persona definition (unverified in Python SDK):
    # "customAgents": [{"slug": "code-reviewer", "name": "Code Reviewer",
    #                    "description": "...", "instructions": "..."}]
})

# send_and_wait() blocks until the full response is ready — no event wiring needed
response = await session.send_and_wait({"prompt": f"Review this diff:\n\n{diff}"})
print(response.data.content)
```

#### Streaming path: `send()` + event handler (for real-time UI updates)

```python
from copilot import CopilotClient
from copilot.generated.session_events import SessionEventType

client = CopilotClient(github_token="github_pat_...")
await client.start()

session = await client.create_session({"model": "gpt-5.4"})

# on() is a plain method, NOT a decorator — pass a callable
def handle_event(event):
    if event.type.value == "assistant.message":
        # event.data.content contains the response (streamed chunks or final)
        print(event.data.content, end="", flush=True)
    elif event.type.value == "session.idle":
        print("\n--- done ---")

session.on(handle_event)

# send() is fire-and-forget — responses arrive via the event handler above
await session.send({"prompt": f"Review this diff:\n\n{diff}"})
```

> **Which path for the review engine?**
> - `send_and_wait()` for MCP tool handlers (need a return value for Claude Code)
> - `send()` + events for the web UI (stream tokens to the dashboard in real-time)
> - Both can coexist in the same session.

#### Key imports

```python
from copilot import CopilotClient                                    # Main client
from copilot.generated.session_events import SessionEventType        # Event enums
from copilot import define_tool                                        # Custom tool definitions
```

### 4.1.1 Useful SDK Features for the Review Server

| Feature | How to use | Purpose |
| ------- | ---------- | ------- |
| `system_message` | `create_session({"system_message": "..."})` | Set reviewer persona/instructions |
| `customAgents` | `create_session({"customAgents": [...]})` | Full agent definition with slug, name, instructions (**unverified — not found in primary Python SDK docs; validate in Phase A**) |
| `github_token` param | `CopilotClient(github_token="github_pat_...")` | Pass token directly — cleaner than env var in Docker |
| `list_models()` | `await client.list_models()` | Discover available models at runtime |
| `on_pre_tool_use` | Hook | Intercept before Copilot calls an MCP tool (logging, approval) |
| `on_post_tool_use` | Hook | Capture tool results for the review transcript |
| `on_session_start` | Hook | Initialize review context |

### 4.2 What Happens Under the Hood

```
┌──────────────┐     spawn      ┌──────────────┐     JSON-RPC     ┌─────────────┐
│  Your Python  │ ────────────► │ copilot CLI   │ ──────────────► │ GitHub      │
│  code         │               │ (server mode) │                 │ Copilot API │
│  (copilot-sdk)│ ◄────────────│               │ ◄────────────── │ (cloud)     │
│              │   JSON-RPC    │ --acp          │   model response│             │
└──────────────┘    responses  └──────────────┘                  └─────────────┘
```

The CLI handles:

- Authentication (GitHub OAuth / `GITHUB_TOKEN` env var)
- Model routing (which Copilot model to use — default: Claude Sonnet 4.6)
- MCP server discovery (if configured)
- Rate limiting and retries

> **Implementation note:** The SDK offers two paths: `send_and_wait()` returns the
> complete response directly (use this for MCP tool handlers), while `send()` +
> `session.on()` streams events (use this for the web UI dashboard). No
> `asyncio.Event` bridging needed — `send_and_wait()` handles it internally.

### 4.3 SDK Capabilities Relevant to Code Review

| Capability | How it helps |
| ---------- | ------------ |
| `send_and_wait()` | Synchronous-style response for MCP tool handlers — no event wiring |
| `send()` + `session.on()` | Streaming for real-time web UI updates |
| `customAgents` / `system_message` | Define reviewer persona directly in session config |
| `github_token` client param | Pass token programmatically — cleaner than env var in Docker |
| `list_models()` | Discover and pick review-optimized models at runtime |
| Lifecycle hooks | `on_pre_tool_use`, `on_post_tool_use` for transcript logging |
| MCP integration | Copilot can use MCP tools too (file reading, etc.) |

---

## 5. Alternative Inner Models

If the Copilot SDK proves too unstable (it's Technical Preview), the same
architecture works with any model inside the review server:

| Inner Model | Setup | Maturity |
| ----------- | ----- | -------- |
| **Copilot SDK** | `github-copilot-sdk` Python package | Technical Preview |
| **OpenAI API** (GPT-5.4, GPT-4o) | `openai` Python package | Production |
| **Anthropic API** (Claude) | `anthropic` Python package | Production |
| **Gemini API** | `google-genai` Python package | Production |
| **Ollama** (local LLM) | HTTP API on localhost:11434 | Production |

The MCP interface to Claude Code stays identical regardless of what's inside.
This makes the architecture model-agnostic.

---

## 6. Exploration Steps

### Phase A: Validate Copilot SDK (1-2 hours)

```bash
# Step 1: Install Copilot CLI
npm install -g @github/copilot
copilot --version

# Step 2: Authenticate (interactive — type /login inside the CLI)
copilot
# > /login
# Follow the device flow prompts, then exit with /exit or Ctrl+C

# Step 3: Test CLI interactively (no -p flag — the CLI is interactive only)
copilot
# > Review this Python function: def add(a, b): return a + b

# Step 4: Install SDK
pip install github-copilot-sdk

# Step 5: Test SDK — simple path (send_and_wait)
python3 -c "
from copilot import CopilotClient
import asyncio

async def main():
    client = CopilotClient()   # Uses GITHUB_TOKEN env var, or pass github_token='github_pat_...'
    await client.start()
    session = await client.create_session({})
    response = await session.send_and_wait({'prompt': 'Say hello'})
    print(response.data.content)

asyncio.run(main())
"

# Step 6: Test SDK — streaming path (send + event handler)
python3 -c "
from copilot import CopilotClient
from copilot.generated.session_events import SessionEventType
import asyncio

async def main():
    client = CopilotClient()
    await client.start()
    session = await client.create_session({})

    done = asyncio.Event()
    def handler(event):
        if event.type.value == 'assistant.message':
            print(event.data.content, end='', flush=True)
        elif event.type.value == 'session.idle':
            print()
            done.set()

    session.on(handler)
    await session.send({'prompt': 'Say hello'})
    await done.wait()

asyncio.run(main())
"

# Step 7: Test ACP server mode (JSON-RPC server for SDK connections)
copilot --acp             # stdio mode (default)
copilot --acp --port 4321 # TCP mode on specified port
```

### Phase B: Build Minimal Review Server (half day)

1. FastAPI app with 2 endpoints: `/review` (start) and `/discuss` (continue)
2. Wrap Copilot SDK in a simple client class
3. Add MCP server using the `mcp` Python package
4. Test with Claude Code: `claude mcp add code-reviewer python -m server.mcp_server`

### Phase C: Add Web UI + Docker (half day)

1. Jinja2 dashboard showing conversation transcripts
2. WebSocket for live updates
3. Dockerize with auth volume mount
4. Test full flow: Claude Code `/develop` → review server → Copilot

### Phase D: Integrate into `/develop` Workflow (future)

Replace or augment the existing `code-review` agent (Step 5 in `/develop`)
with an MCP call to the review server, enabling Copilot as an external reviewer
alongside Claude's self-review.

---

## 7. Design Decisions

### 7.1 File Access: What the Container Can See

The container gets a **curated, read-only snapshot** — not a full repo mount.
Claude Code prepares a review bundle and passes it via the MCP tool call.

#### Allowed (read-only, copied into container volume)

| Category | Files | Why |
| -------- | ----- | --- |
| **Changed files (full)** | Every file in the diff, complete content | Reviewer needs surrounding context, not just hunks |
| **Test files** | Test files for changed components (`.test.jsx`, `test_*.py`) | Verify test coverage and quality |
| **Spec artifacts** | `specs/issue-NN-slug/spec.md`, `plan.md`, `tasks.md` | The "why" — what was the task, acceptance criteria |
| **Project rules** | `CLAUDE.md` (conventions section only) | Coding standards, forbidden patterns, naming rules |
| **Anti-patterns** | `.claude/anti-patterns.md` | Known mistakes to scan for |
| **ADRs (relevant)** | Only ADRs referenced in the spec or changed files | Architectural decisions that constrain the change |
| **Git diff** | `git diff main...HEAD` output | The raw change set |
| **Test results** | stdout/stderr from test runs | Did tests pass? Coverage delta? |

#### Blocked (never enters the container)

| Category | Examples | Why |
| -------- | -------- | --- |
| **Secrets** | `.env`, `*.pem`, `*credentials*`, `GITHUB_TOKEN` | Security — container runs third-party model |
| **Auth state** | `.claude/`, `memory-bank/`, `.git/credentials` | Claude's private memory and session state |
| **Git history** | `.git/` directory | Large, unnecessary, and contains auth config |
| **Dependencies** | `node_modules/`, `.venv/`, `__pycache__/` | Massive, not useful for review |
| **Build artifacts** | `dist/`, `htmlcov/`, `coverage/` | Generated, not reviewable |
| **Other agents** | `.claude/agents/`, `.claude/skills/` | Internal orchestration — not the reviewer's concern |
| **CI/CD** | `.github/workflows/` | Not relevant to code review |

#### How it works in practice

Claude Code doesn't mount the repo. Instead, the `start_review` MCP tool accepts
structured data:

```text
start_review(
  diff:         string    — git diff output
  files:        dict      — { "path": "full content" } for each changed file
  test_files:   dict      — { "path": "full content" } for related test files
  spec:         string    — concatenated spec artifacts (spec.md + tasks.md)
  conventions:  string    — extracted CLAUDE.md rules section
  anti_patterns: string   — .claude/anti-patterns.md content
  test_results: string    — test runner stdout/stderr
  context:      string    — free-form: PR description, issue title, etc.
)
```

This means:
- **No volume mounts needed** — data arrives via the MCP tool call
- **Claude Code decides** what to include (it reads the files, curates, sends)
- **Container is stateless** — nothing persists between reviews
- **No file system attack surface** — the container can't traverse the host

> **Trade-off:** This limits the reviewer to files Claude explicitly sends. If the
> reviewer asks "what does `api.js` export?", Claude would need to send it via a
> follow-up `discuss()` call. This is intentional — the reviewer should not have
> unsupervised access to browse the repo.

---

### 7.2 Localhost UI: Review Transcript Monitor

No React app, no SPA. A server-rendered page that looks like a structured log viewer.

#### Layout

```text
┌─────────────────────────────────────────────────────────────────────┐
│  Review Monitor                                    localhost:8080   │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                     │
│  Sessions                                                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ ● review-a1b2  feature/issue-198  3 rounds  RESOLVED  2m ago  │ │
│  │ ○ review-c3d4  feature/issue-188  1 round   ACTIVE    now     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ━━━ review-c3d4 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                     │
│  14:23:01  SYSTEM   Session started                                 │
│            FILES    VideoSection.jsx, VideoSection.test.jsx (+2)    │
│            SPEC     issue-198: fix intermittent iframe controls     │
│                                                                     │
│  14:23:02  CLAUDE → COPILOT                                        │
│            Review this diff against the spec and project rules.     │
│            [diff: +47 -12 across 3 files]                          │
│                                                                     │
│  14:23:08  COPILOT → CLAUDE                              6.2s      │
│            Found 3 issues:                                          │
│            ┌──────────────────────────────────────────────────────┐ │
│            │ 1. BUG  VideoSection.jsx:45                         │ │
│            │   useEffect cleanup doesn't abort pending iframe    │ │
│            │   load — race condition on rapid language switch     │ │
│            │                                                      │ │
│            │ 2. WARN VideoSection.jsx:62                         │ │
│            │   sandbox attr missing allow-popups-to-escape-      │ │
│            │   sandbox — breaks "Watch on YouTube" link          │ │
│            │                                                      │ │
│            │ 3. NIT  VideoSection.test.jsx:89                    │ │
│            │   Test name doesn't describe expected behavior      │ │
│            └──────────────────────────────────────────────────────┘ │
│                                                                     │
│  14:23:10  CLAUDE → COPILOT                                        │
│            Re: #2 — allow-popups-to-escape-sandbox is already      │
│            present in the existing code (line 58, not in diff).    │
│            The diff only modifies the onLoad handler. Dismissing.  │
│                                                                     │
│  14:23:14  COPILOT → CLAUDE                              3.8s      │
│            You're right, I missed that #2 is outside the diff.     │
│            Withdrawn. #1 and #3 stand.                             │
│                                                                     │
│  14:23:15  SYSTEM   Round 1 complete: 1 BUG, 0 WARN, 1 NIT       │
│                     Claude accepted: 2  Dismissed: 1               │
│                                                                     │
│  ─── end of transcript (auto-refreshes every 2s) ──────────────── │
│                                                                     │
│  Raw JSON ▸                                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### Technical implementation

| Aspect | Choice | Why |
| ------ | ------ | --- |
| Rendering | Server-side Jinja2 templates | No JS framework needed |
| Live updates | `<meta http-equiv="refresh" content="2">` or SSE | Simplest possible — no WebSocket complexity |
| Styling | Single CSS file, monospace font, dark theme | Log viewer aesthetic |
| Data | SQLite file or in-memory list | Sessions + messages, that's it |
| Collapsible sections | `<details>/<summary>` HTML | Native, no JS needed for "Raw JSON" toggle |
| Export | `/api/sessions/{id}/export` → JSON download | For post-mortem / archival |

#### Pages

| Route | Purpose |
| ----- | ------- |
| `GET /` | Session list (table with status, branch, round count, age) |
| `GET /session/{id}` | Full transcript for one session (the log view above) |
| `GET /session/{id}/raw` | Raw JSON of all messages |
| `GET /api/sessions/{id}/export` | Download JSON for archival |

No login, no auth — it's localhost only. If the port is exposed, that's
the operator's problem (and Docker defaults to binding `127.0.0.1` anyway).

---

### 7.3 Review Context: What Claude Sends for Maximum Quality

The goal is to make the external reviewer **as effective as a human reviewer
who has read the issue, spec, and conventions**. Diff alone is insufficient.

#### The Review Bundle

Claude Code assembles this before calling `start_review`:

```text
┌─────────────────────────────────────────────────────────┐
│                    REVIEW BUNDLE                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. TASK CONTEXT (the "why")                            │
│     ├── Issue title + description                       │
│     ├── spec.md — requirements, acceptance criteria     │
│     └── tasks.md — checklist of what was implemented    │
│                                                         │
│  2. THE CHANGE (the "what")                             │
│     ├── git diff main...HEAD (unified diff)             │
│     ├── Full content of every changed file              │
│     └── List of files added / deleted / modified        │
│                                                         │
│  3. TEST EVIDENCE (the "proof")                         │
│     ├── Related test files (full content)               │
│     ├── Test runner output (pass/fail + coverage)       │
│     └── Lint output (if any warnings)                   │
│                                                         │
│  4. PROJECT RULES (the "standards")                     │
│     ├── CLAUDE.md conventions section                   │
│     │   (no TS, no CSS frameworks, semantic HTML,       │
│     │    functional components, mobile-first, etc.)     │
│     ├── anti-patterns.md (AP-001 through AP-028)        │
│     └── Relevant ADR summaries (if referenced in spec)  │
│                                                         │
│  5. REVIEW INSTRUCTIONS (the "how")                     │
│     └── System prompt telling the reviewer:             │
│         - Check diff against spec (completeness)        │
│         - Check against conventions (compliance)        │
│         - Check against anti-patterns (known mistakes)  │
│         - Verify tests cover the change                 │
│         - Classify findings: BUG / WARN / NIT           │
│         - Include file:line references                  │
│         - Don't flag things outside the diff            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### Why each piece matters

| Piece | Without it | With it |
| ----- | ---------- | ------- |
| Spec + tasks | Reviewer can only check "does code look right" | Reviewer can check "does code do what was asked" |
| Full files (not just diff) | Reviewer can't see surrounding context, misses interactions | Reviewer catches "you added X but the existing Y on line 30 conflicts" |
| Test files | Reviewer can say "add tests" generically | Reviewer can say "your test on line 45 doesn't cover the error path" |
| Test results | Reviewer has to trust "tests pass" claim | Reviewer sees actual output, coverage numbers |
| Anti-patterns | Reviewer invents its own standards | Reviewer checks against real project history of mistakes |
| Conventions | Reviewer uses generic best practices | Reviewer enforces THIS project's specific rules |

#### Multi-turn enrichment

During `discuss()` rounds, Claude can send additional context on demand:

```text
discuss(session_id, message, additional_files={
  "src/config/api.js": "<full content>"
})
```

This handles the case where the reviewer asks "what does this import do?" —
Claude reads the file and sends it in the next message, without giving the
container direct file system access.

---

## 8. A2A Protocol — Now v1.0.0 GA

> **Updated 2026-03-12:** A2A reached v1.0.0 stable release on this date.

The A2A (Agent-to-Agent) protocol moved from experimental to production-ready:

- **v1.0.0 stable specification** released
- Official SDKs: Python, Go, JavaScript, Java, .NET
- Repo moved from `google/A2A` to `a2aproject/A2A` (Linux Foundation AAIF)
- 22.5k stars, 145 contributors
- DeepLearning.AI course available

### What this means for this project

A2A is now a **medium-term viable option**, not just speculative. Two paths:

| Approach | How | When to use |
| -------- | --- | ----------- |
| **MCP-first** (recommended) | Review server exposes MCP tools to Claude Code | Now — Claude Code speaks MCP natively |
| **A2A-native** | Review server is an A2A agent; Claude Code reaches it via A2A-MCP bridge | When A2A-MCP bridges mature or Claude Code adds native A2A |

The MCP-first approach (Path 3) remains the pragmatic choice because Claude Code
already speaks MCP. But A2A is worth watching — if Claude Code gains native A2A
support, the review server could expose itself as an A2A agent directly, which is
a cleaner protocol fit (agent-to-agent vs agent-to-tool).

---

## 9. Open Questions

- [x] Does the Copilot SDK Python package support macOS ARM64 (Apple Silicon)?
      → Yes: PyPI ships a `macosx_11_0_arm64` wheel (55.3 MB).
- [ ] What's the rate limit on Copilot SDK calls? (tied to subscription tier?)
- [ ] Can Copilot SDK access the repo context (file tree, git history) in server mode?
      (Design decision: we don't rely on this — context comes via MCP tool calls)
- [ ] How does Copilot SDK handle large diffs? (token limits?)
- [x] Is there a way to configure which Copilot model is used for review?
      → Yes: `client.create_session({"model": "gpt-5.4"})` + `list_models()` at runtime
- [ ] Does the Copilot CLI server mode work inside Docker without a TTY?
      (Critical — must validate in Phase A)
- [x] Auth in Docker: can we use a GitHub PAT, or does it require OAuth device flow?
      → PAT via `GITHUB_TOKEN` env var works. Design uses PAT with web UI setup wizard.
- [x] Does the `copilot` scope exist on fine-grained PATs, or only classic tokens?
      → Fine-grained PATs use the `copilot_requests` (write) permission, not an OAuth scope.
        Classic PATs are not supported by Copilot CLI/SDK at all.
- [ ] Image size: Python 3.11 + Node 20 + Copilot CLI — how big is the final image?
- [ ] Can we publish to ghcr.io for easy `docker pull` by colleagues?

---

## 10. References

| Resource | URL |
| -------- | --- |
| Copilot CLI (npm) | <https://github.com/github/copilot-cli> |
| Copilot SDK (GitHub) | <https://github.com/github/copilot-sdk> |
| Copilot SDK blog post | <https://github.blog/news-insights/company-news/build-an-agent-into-any-app-with-the-github-copilot-sdk/> |
| MCP Python SDK | <https://github.com/modelcontextprotocol/python-sdk> |
| A2A Protocol (v1.0.0) | <https://github.com/a2aproject/A2A> |
| a2a-copilot (A2A wrapper) | <https://github.com/shashikanth-gs/a2a-copilot> |
| A2A-MCP Bridge | <https://github.com/GongRzhe/A2A-MCP-Server> |
| Copilot CLI docs | <https://docs.github.com/copilot/concepts/agents/about-copilot-cli> |
| Copilot Extensions docs | <https://docs.github.com/copilot/concepts/extensions/agents> |
