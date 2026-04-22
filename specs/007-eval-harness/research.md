# Research: Eval Harness (007)

**Date**: 2026-03-31
**Purpose**: Resolve technical unknowns before design — 4 open decisions from specify phase + 4 additional design decisions

## Decision 1: Eval Package Location

**Decision**: `eval/` at repository root

**Rationale**: The eval harness is a standalone CLI tool, not a regular test suite. It has its own entry point (`python -m eval`), its own fixtures, and its own dependency (Anthropic API for the Tier 2 grader). The separation is conceptual: `tests/` contains pytest unit/integration tests for the codebase internals, while `eval/` is a tool that exercises the live reviewer through its MCP interface. This mirrors the Inspect AI pattern (separate eval package, separate test suite).

**Alternatives rejected**:
- `tests/eval/` — conflates two different testing concerns (unit tests vs system-level evaluation). Running `pytest` would pick up eval fixtures as test data. The eval harness needs its own CLI, not pytest discovery.
- `tools/eval/` — `eval/` is simpler and the harness is the only standalone tool in the project.

## Decision 2: Golden Case Storage

**Decision**: `eval/fixtures/` inside the repository, versioned alongside harness code

**Rationale**: Golden cases must be version-locked to the grader prompt they were calibrated against (FR-022). If cases live in a separate repo, prompt/case version drift is inevitable. The total fixture size for 20-30 cases (diffs + small source files + JSON manifests) is under 1 MB — well within repo limits. Cases are stored as self-contained directories per FR-003.

**Alternatives rejected**:
- Separate fixtures repo — adds clone step, version coordination overhead, and CI complexity. No benefit for <1 MB of fixtures.
- Git LFS — overkill for small text-only fixtures.

## Decision 3: MCP Transport Mechanism

**Decision**: `docker exec -i` via the MCP Python SDK's `stdio_client` + `ClientSession`

**Rationale**: This is the exact same transport Claude Code uses in production. The eval should test the real communication path, not a shortcut. The MCP Python SDK (`mcp>=1.0.0`) provides a client API: `StdioServerParameters` specifies the command, `stdio_client()` spawns it as a subprocess and provides read/write channels, and `ClientSession` handles JSON-RPC protocol.

**Pattern**:
```python
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

server_params = StdioServerParameters(
    command="docker",
    args=["exec", "-i", container_name, "python", "-m", "server.mcp_server"],
)
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("start_review", arguments={...})
```

**Validation**: Confirmed via MCP Python SDK docs and PyPI (`mcp>=1.7.1`). The `stdio_client` function spawns the command as a subprocess and communicates via stdin/stdout streams. Docker's `-i` flag keeps stdin open for the subprocess.

**Alternatives rejected**:
- Raw subprocess + manual JSON-RPC — reinvents the MCP client protocol, error-prone, no benefit.
- StreamableHTTP transport — requires exposing an HTTP endpoint on the container, adds CORS/auth complexity. Stdio is the native transport for single-client use.
- Direct Python import (no Docker) — bypasses the security boundary and container isolation. Wouldn't test the real deployment path.

## Decision 4: Grader Model Selection

**Decision**: Anthropic Claude (via `anthropic` Python SDK), configurable via `--grader-model` CLI flag. Default: `claude-sonnet-4-6`.

**Rationale**: The grader must differ from the evaluated model (FR-020). The reviewer uses Copilot (GPT-family models); using Claude as the grader guarantees model independence. Claude Sonnet provides strong reasoning for semantic matching at lower cost than Opus. The `anthropic` SDK runs on the host (not in the container), so the API key never enters the Docker boundary — respecting constitution Principle III.

**Pattern**:
```python
import anthropic

client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": grader_prompt}],
)
```

**Validation**: Confirmed via Anthropic Python SDK docs (PyPI `anthropic>=0.86.0`). `messages.create()` API is current. Model IDs follow the `claude-{tier}-{version}` pattern.

**Alternatives rejected**:
- Using Copilot SDK for grading — would mean the graded model and grader share the same provider, risking correlation. Also requires the grader to run inside the container.
- OpenAI API — viable but adds another API key dependency. Claude is native to this project's ecosystem.
- Local Ollama — insufficient reasoning quality for semantic finding matching. Model-based grading requires strong instruction following.

## Decision 5: Harness Execution Environment

**Decision**: Host machine (outside Docker). The eval harness is a Python CLI that runs on the developer's machine or in CI.

**Rationale**: The harness needs to (a) spawn `docker exec` to communicate with the reviewer container, (b) call the Anthropic API for Tier 2 grading, and (c) write output files. All three are host-side operations. Running the harness inside a separate container would add Docker-in-Docker complexity with no benefit.

**For CI**: GitHub Actions runs the harness directly on the runner. The reviewer container is started via `docker compose up -d`, then the harness communicates via `docker exec`.

**Alternatives rejected**:
- Eval in a second Docker container — Docker-in-Docker or sibling container adds complexity. The harness doesn't need isolation; it's a developer tool.

## Decision 6: CLI Framework

**Decision**: `argparse` (stdlib). No external CLI framework.

**Rationale**: The CLI has ~10 flags. `argparse` handles this cleanly. Constitution Principle VI: no unnecessary dependencies. `click` or `typer` add value for complex CLIs with subcommands, not for a single-command tool.

**Alternatives rejected**:
- `click` — dependency for marginal benefit at this scale.
- `typer` — Pydantic-powered but adds a dependency and magic we don't need.

## Decision 7: Output and Baseline Format

**Decision**: JSON for machine-readable output, Markdown for human-readable scorecards. Baseline comparison uses JSON diff.

**Rationale**: FR-009 requires both formats. JSON is the canonical format for CI consumption and baseline comparison. Markdown is generated from the JSON scorecard for PR comments (FR-012a) and terminal output. The baseline file is a previous run's JSON output, loaded with `--baseline path/to/baseline.json`.

**Storage**: Results are written to an output directory (`--output-dir`, default: `eval/results/`). Each run produces `run-{timestamp}.json` and `scorecard-{timestamp}.md`.

## Decision 8: Retry and Rate Limit Strategy

**Decision**: Exponential backoff with jitter per FR-013. Per-case retries, not per-run restarts.

**Rationale**: The reviewer (Copilot) may rate-limit under load. Retrying individual cases is cheaper than restarting the entire eval run. Maximum 3 retries per case with 2^n * 1s + random jitter backoff. Cases that exhaust retries are marked as `error` in results (distinct from `fail`).

**Alternatives rejected**:
- Global retry (restart full run) — wastes successful case results.
- No retry (fail immediately) — FR-013 explicitly requires retry with backoff.

## Open Questions (for build phase)

1. **Grader prompt calibration data**: Need ~30+ human-labeled examples to calibrate Tier 2. This is a build-phase effort — start with 5-10 examples and expand.
2. **Container name discovery**: The eval CLI needs to know the container name/ID. Default: read from `docker compose ps` or accept `--container` flag.
3. **Parallel case execution**: Cases are independent and run in parallel with `asyncio.Semaphore(concurrency)` (default 5). Implemented in release phase after sequential execution exceeded the 30 min target (SC-001).
