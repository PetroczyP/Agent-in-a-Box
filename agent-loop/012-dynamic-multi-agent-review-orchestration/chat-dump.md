╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                                                           │
│                                                                                                                                                             │
│ Spec 012 Evolution: Dynamic Multi-Agent Review Orchestration                                                                                                │
│                                                                                                                                                             │
│ Context                                                                                                                                                     │
│                                                                                                                                                             │
│ Spec 012 (Multi-Dimension Review) currently defines static persona dispatch — the caller manually picks standard, thorough, or focused mode. This evolution │
│  adds dynamic orchestration: an LLM classifier analyzes the PR's nature, the project's architectural context, and caller hints to automatically decide      │
│ which specialized review agents to spawn. Inspired by the SAGE reviewer's orchestrator pattern and the pr-review-toolkit's specialized agent model.         │
│                                                                                                                                                             │
│ Problem: Single-pass LLM reviews suffer from attention distribution limits ("drip-feed discovery") and single-persona bias. Static multi-persona dispatch   │
│ (spec 012 as-is) helps but requires the caller to know which perspectives matter. Dynamic orchestration makes the system self-routing.                      │
│                                                                                                                                                             │
│ Outcome: A review server that accepts architectural context (CLAUDE.md, copilot-instructions), analyzes the PR, spawns the right specialized agents, and    │
│ synthesizes findings — all transparently to the caller.                                                                                                     │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Architecture: Orchestrator-as-Middleware (Approach A)                                                                                                       │
│                                                                                                                                                             │
│ MCP start_review(diff, files, ..., review_mode, project_rules, personas)                                                                                    │
│ │                                                                                                                                                           │
│ ├─ mode="standard" → ReviewEngine.start_review() [unchanged]                                                                                                │
│ │                                                                                                                                                           │
│ └─ mode="auto"|"thorough"|"focused"                                                                                                                         │
│    │                                                                                                                                                        │
│    ├─ ReviewOrchestrator.run(bundle)                                                                                                                        │
│    │  │                                                                                                                                                     │
│    │  ├─ 1. Signal Extraction                                                                                                                               │
│    │  │     • file_paths, extensions, diff_size, diff_shape                                                                                                 │
│    │  │     • project_rules keywords (tech stack, frameworks)                                                                                               │
│    │  │     • caller hints (context param, personas list)                                                                                                   │
│    │  │                                                                                                                                                     │
│    │  ├─ 2. Classifier (auto mode only)                                                                                                                     │
│    │  │     • Single LLM call (cheapest available model, ~200ms)                                                                                            │
│    │  │     • Input: signal summary (~2000 chars)                                                                                                           │
│    │  │     • Output: {"agents": [...], "rationale": "..."}                                                                                                 │
│    │  │     • Always includes "correctness" as baseline                                                                                                     │
│    │  │                                                                                                                                                     │
│    │  ├─ 3. Parallel Agent Dispatch                                                                                                                         │
│    │  │     • asyncio.gather(*agent_coroutines, return_exceptions=True)                                                                                     │
│    │  │     • Per-agent timeout: AGENT_TIMEOUT env var (default 60s)                                                                                        │
│    │  │     • Each agent: own Copilot session + system prompt + full bundle                                                                                 │
│    │  │     • Partial success: if some agents fail, others' findings preserved                                                                              │
│    │  │                                                                                                                                                     │
│    │  ├─ 4. Judge (dedicated LLM call, best available model)                                                                                                │
│    │  │     • Semantic dedup (same issue, different wording → merge)                                                                                        │
│    │  │     • Severity reconciliation (agents disagree → pick higher)                                                                                       │
│    │  │     • Pattern consolidation (same issue in 5 files → 1 finding)                                                                                     │
│    │  │     • Cross-agent insight escalation                                                                                                                │
│    │  │     • Fabrication guardrail: findings not traceable to agents → low confidence                                                                      │
│    │  │                                                                                                                                                     │
│    │  └─ 5. Return unified findings + agent metadata                                                                                                        │
│    │                                                                                                                                                        │
│    └─ ReviewEngine.create_session_from_findings(bundle, findings, metadata)                                                                                 │
│       (session creation, storage, idempotency — reuses existing logic)                                                                                      │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ API Surface Changes                                                                                                                                         │
│                                                                                                                                                             │
│ start_review — 3 new optional parameters                                                                                                                    │
│                                                                                                                                                             │
│ async def start_review(                                                                                                                                     │
│     # Existing (unchanged):                                                                                                                                 │
│     diff: str, files: dict[str, str],                                                                                                                       │
│     test_files: dict[str, str] | None = None,                                                                                                               │
│     spec: str | None = None,                                                                                                                                │
│     conventions: str | None = None,                                                                                                                         │
│     anti_patterns: str | None = None,                                                                                                                       │
│     test_results: str | None = None,                                                                                                                        │
│     context: str | None = None,                                                                                                                             │
│     branch: str | None = None,                                                                                                                              │
│     model: str | None = None,                                                                                                                               │
│     idempotency_token: str | None = None,                                                                                                                   │
│     # New:                                                                                                                                                  │
│     review_mode: str | None = None,       # "auto" (default) | "standard" | "thorough" | "focused"                                                          │
│     personas: list[str] | None = None,    # For "focused" only: ["security", "architecture"]                                                                │
│     project_rules: str | None = None,     # CLAUDE.md / copilot-instructions content                                                                        │
│ ) -> dict:                                                                                                                                                  │
│                                                                                                                                                             │
│ Default is "auto" — the classifier decides. Existing callers get smarter reviews without code changes. The classifier may still select single-agent for     │
│ trivial diffs.                                                                                                                                              │
│                                                                                                                                                             │
│ get_review_summary — extended response                                                                                                                      │
│                                                                                                                                                             │
│ Adds per-agent breakdown in the summary:                                                                                                                    │
│ {                                                                                                                                                           │
│   "agent_stats": {                                                                                                                                          │
│     "correctness": {"findings": 2, "duration_ms": 3400, "success": true},                                                                                   │
│     "security": {"findings": 1, "duration_ms": 2800, "success": true}                                                                                       │
│   },                                                                                                                                                        │
│   "classifier_rationale": "PR touches auth middleware → security + correctness + architecture",                                                             │
│   "review_mode_used": "auto",                                                                                                                               │
│   "agents_selected": ["correctness", "security", "architecture"]                                                                                            │
│ }                                                                                                                                                           │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Model Tiering                                                                                                                                               │
│                                                                                                                                                             │
│ Built-in Tier Mapping + Env Overrides                                                                                                                       │
│                                                                                                                                                             │
│ Copilot SDK reality: list_models() returns string IDs only — no capability metadata, no tier API, no "auto" task-routing. GitHub's Chat "auto" is an        │
│ availability router, not a task-complexity router. We must maintain our own tier mapping.                                                                   │
│                                                                                                                                                             │
│ New file: server/model_tiers.py                                                                                                                             │
│                                                                                                                                                             │
│ TIER_MAP = {                                                                                                                                                │
│     "fast":  ["gpt-4o-mini", "gpt-3.5-turbo"],           # Classifier                                                                                       │
│     "mid":   ["gpt-4o", "gpt-4-turbo"],                   # Review agents                                                                                   │
│     "best":  ["gpt-4o", "gpt-4-turbo", "gpt-4"],          # Judge                                                                                           │
│ }                                                                                                                                                           │
│                                                                                                                                                             │
│ def pick_best(available: list[str], tier_preference: list[str]) -> str:                                                                                     │
│     """Return the first model from tier_preference that's in available."""                                                                                  │
│     for model in tier_preference:                                                                                                                           │
│         if model in available:                                                                                                                              │
│             return model                                                                                                                                    │
│     return available[0]  # fallback to whatever's available                                                                                                 │
│                                                                                                                                                             │
│ At startup, the orchestrator calls list_models() once and resolves tier assignments. Env var overrides always win. The existing model param on start_review │
│  acts as a blanket override (all stages use it).                                                                                                            │
│                                                                                                                                                             │
│ Maintenance: When GitHub adds new models, update TIER_MAP in the next release. Between releases, users can override via env vars.                           │
│                                                                                                                                                             │
│ Configuration                                                                                                                                               │
│                                                                                                                                                             │
│ ┌──────────────────┬───────────────────────────────┬──────────────────────────────────┐                                                                     │
│ │     Env Var      │            Default            │             Purpose              │                                                                     │
│ ├──────────────────┼───────────────────────────────┼──────────────────────────────────┤                                                                     │
│ │ CLASSIFIER_MODEL │ auto (cheapest from TIER_MAP) │ Override classifier model        │                                                                     │
│ ├──────────────────┼───────────────────────────────┼──────────────────────────────────┤                                                                     │
│ │ AGENT_MODEL      │ auto (mid-tier from TIER_MAP) │ Override all review agent models │                                                                     │
│ ├──────────────────┼───────────────────────────────┼──────────────────────────────────┤                                                                     │
│ │ JUDGE_MODEL      │ auto (best from TIER_MAP)     │ Override judge model             │                                                                     │
│ ├──────────────────┼───────────────────────────────┼──────────────────────────────────┤                                                                     │
│ │ AGENT_TIMEOUT    │ 60                            │ Per-agent timeout in seconds     │                                                                     │
│ └──────────────────┴───────────────────────────────┴──────────────────────────────────┘                                                                     │
│                                                                                                                                                             │
│ Zero-config default: docker compose up -d just works. Built-in tier mapping picks from available models.                                                    │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Review Modes                                                                                                                                                │
│                                                                                                                                                             │
│ ┌────────────────┬────────────┬─────────────────────────┬───────┬──────────────────────────────────┐                                                        │
│ │      Mode      │ Classifier │         Agents          │ Judge │             Use Case             │                                                        │
│ ├────────────────┼────────────┼─────────────────────────┼───────┼──────────────────────────────────┤                                                        │
│ │ auto (default) │ Yes        │ Classifier-selected     │ Yes   │ Most reviews — system decides    │                                                        │
│ ├────────────────┼────────────┼─────────────────────────┼───────┼──────────────────────────────────┤                                                        │
│ │ standard       │ No         │ None (single-pass)      │ No    │ Backward compat, trivial changes │                                                        │
│ ├────────────────┼────────────┼─────────────────────────┼───────┼──────────────────────────────────┤                                                        │
│ │ thorough       │ No         │ All 5                   │ Yes   │ Critical PRs, release candidates │                                                        │
│ ├────────────────┼────────────┼─────────────────────────┼───────┼──────────────────────────────────┤                                                        │
│ │ focused        │ No         │ Caller-specified subset │ Yes   │ Known concern areas              │                                                        │
│ └────────────────┴────────────┴─────────────────────────┴───────┴──────────────────────────────────┘                                                        │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Agent Roster (5 Concern-Based Agents)                                                                                                                       │
│                                                                                                                                                             │
│ ┌──────────────┬─────────────────────────────────────────────────┬────────────────────────────────────────────────────────────────────────┐                 │
│ │    Agent     │                      Focus                      │                          Key Checklist Items                           │                 │
│ ├──────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤                 │
│ │ correctness  │ Bugs, logic errors, edge cases, null handling   │ Off-by-one, race conditions, error propagation, boundary values        │                 │
│ ├──────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤                 │
│ │ security     │ Vulnerabilities, injection, auth, secrets       │ OWASP top 10, input validation, auth/authz gaps, secret exposure       │                 │
│ ├──────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤                 │
│ │ design       │ Code-level quality: naming, abstractions, SOLID │ Single responsibility, DRY, coupling, API ergonomics                   │                 │
│ ├──────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤                 │
│ │ tests        │ Coverage gaps, test quality, missing edge cases │ Untested paths, assertion quality, test isolation, error case coverage │                 │
│ ├──────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤                 │
│ │ architecture │ Project-level: patterns, deps, API contracts    │ project_rules compliance, dependency direction, contract consistency   │                 │
│ └──────────────┴─────────────────────────────────────────────────┴────────────────────────────────────────────────────────────────────────┘                 │
│                                                                                                                                                             │
│ Agent File Structure                                                                                                                                        │
│                                                                                                                                                             │
│ server/agents/                                                                                                                                              │
│ ├── __init__.py          # AgentConfig dataclass, AgentRegistry dict                                                                                        │
│ ├── correctness.py       # CORRECTNESS_PROMPT, CORRECTNESS_CHECKLIST                                                                                        │
│ ├── security.py                                                                                                                                             │
│ ├── design.py                                                                                                                                               │
│ ├── tests.py                                                                                                                                                │
│ └── architecture.py                                                                                                                                         │
│                                                                                                                                                             │
│ AgentConfig                                                                                                                                                 │
│                                                                                                                                                             │
│ @dataclass                                                                                                                                                  │
│ class AgentConfig:                                                                                                                                          │
│     name: str                     # "correctness"                                                                                                           │
│     system_prompt: str            # Full persona prompt with checklist + output schema                                                                      │
│     checklist: list[str]          # Mandatory items the agent must address                                                                                  │
│     enabled_by_default: bool      # True for all 5 (used by thorough mode)                                                                                  │
│                                                                                                                                                             │
│ Each agent's system prompt includes:                                                                                                                        │
│ - Role definition and focus area                                                                                                                            │
│ - Mandatory checklist (must address each item even if no findings)                                                                                          │
│ - Output schema (same JSON format as current REVIEWER_PERSONA)                                                                                              │
│ - project_rules injection point (if provided)                                                                                                               │
│ - Language/framework context derived from project_rules (not a separate agent)                                                                              │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Classifier Design                                                                                                                                           │
│                                                                                                                                                             │
│ File: server/review_classifier.py                                                                                                                           │
│                                                                                                                                                             │
│ async def classify_review(                                                                                                                                  │
│     diff_summary: str,        # First 2000 chars + file list + line counts                                                                                  │
│     project_rules: str | None,                                                                                                                              │
│     caller_hints: str | None,  # context param content                                                                                                      │
│     personas_hint: list[str] | None,  # caller's persona suggestions                                                                                        │
│     copilot: CopilotReviewClient,                                                                                                                           │
│     model: str | None = None,                                                                                                                               │
│ ) -> ClassifierResult:                                                                                                                                      │
│     # Returns: {"agents": ["correctness", "security"], "rationale": "..."}                                                                                  │
│                                                                                                                                                             │
│ Classifier prompt design:                                                                                                                                   │
│ - Lists all 5 available agents with their focus descriptions                                                                                                │
│ - Instructs: "Select the agents most relevant to this PR. Always include correctness."                                                                      │
│ - Provides signals: file list, diff size, project_rules summary, caller hints                                                                               │
│ - Output: strict JSON, no prose                                                                                                                             │
│ - Timeout: 5s (if classifier hangs, fall back to all agents — safe default)                                                                                 │
│                                                                                                                                                             │
│ Cost control: The classifier can select as few as 1 agent (correctness only for trivial PRs) or all 5 for complex changes. The LLM decides proportionally.  │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Judge Design                                                                                                                                                │
│                                                                                                                                                             │
│ File: server/review_judge.py                                                                                                                                │
│                                                                                                                                                             │
│ async def judge_findings(                                                                                                                                   │
│     agent_results: list[AgentResult],                                                                                                                       │
│     diff: str,                                                                                                                                              │
│     project_rules: str | None,                                                                                                                              │
│     copilot: CopilotReviewClient,                                                                                                                           │
│     model: str | None = None,                                                                                                                               │
│ ) -> list[Finding]:                                                                                                                                         │
│                                                                                                                                                             │
│ Judge behaviors:                                                                                                                                            │
│ 1. Semantic dedup: Two agents flag same underlying issue → merge, source_persona lists both                                                                 │
│ 2. Severity reconciliation: Agents disagree on severity → judge picks higher with explanation                                                               │
│ 3. Pattern consolidation: Same issue in N files → 1 finding with all locations in related_locations                                                         │
│ 4. Cross-agent escalation: Correctness bug with security implications → judge can upgrade severity                                                          │
│ 5. Fabrication guardrail: Any finding not traceable to agent input → confidence: low, rule_id: judge-fabrication                                            │
│                                                                                                                                                             │
│ No approval recommendation — unlike SAGE, this is a review tool, not a gate. Findings with severity only.                                                   │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Integration with ReviewEngine                                                                                                                               │
│                                                                                                                                                             │
│ New method (no changes to existing start_review)                                                                                                            │
│                                                                                                                                                             │
│ # server/review_engine.py — NEW method                                                                                                                      │
│ async def create_session_from_findings(                                                                                                                     │
│     self,                                                                                                                                                   │
│     bundle: ReviewBundle,                                                                                                                                   │
│     findings: list[Finding],                                                                                                                                │
│     agent_metadata: dict,                                                                                                                                   │
│ ) -> ReviewResult:                                                                                                                                          │
│     """Create a review session from pre-synthesized findings.                                                                                               │
│                                                                                                                                                             │
│     Reuses: idempotency check, session creation, session storage.                                                                                           │
│     Skips: copilot call, finding parsing (already done by orchestrator).                                                                                    │
│     """                                                                                                                                                     │
│                                                                                                                                                             │
│ MCP server routing                                                                                                                                          │
│                                                                                                                                                             │
│ # server/mcp_server.py                                                                                                                                      │
│ if bundle.review_mode == "standard":                                                                                                                        │
│     result = await engine.start_review(bundle)                                                                                                              │
│ else:                                                                                                                                                       │
│     findings, metadata = await orchestrator.run(bundle)                                                                                                     │
│     result = await engine.create_session_from_findings(bundle, findings, metadata)                                                                          │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Context Assembly                                                                                                                                            │
│                                                                                                                                                             │
│ build_review_context() in server/prompts.py gains a new section:                                                                                            │
│                                                                                                                                                             │
│ Order: conventions → project_rules → anti_patterns → spec → diff → files → test_files → test_results → context → format reinforcement                       │
│                                                                                                                                                             │
│ The project_rules section is injected early (high attention weight due to primacy) so agents can reference it throughout their analysis. Each agent         │
│ receives the same assembled context but with their own system prompt focusing attention.                                                                    │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Model Changes (server/models.py)                                                                                                                            │
│                                                                                                                                                             │
│ class ReviewMode(str, Enum):                                                                                                                                │
│     AUTO = "auto"                                                                                                                                           │
│     STANDARD = "standard"                                                                                                                                   │
│     THOROUGH = "thorough"                                                                                                                                   │
│     FOCUSED = "focused"                                                                                                                                     │
│                                                                                                                                                             │
│ @dataclass                                                                                                                                                  │
│ class AgentResult:                                                                                                                                          │
│     agent_name: str                                                                                                                                         │
│     findings: list[Finding]                                                                                                                                 │
│     duration_ms: float                                                                                                                                      │
│     success: bool                                                                                                                                           │
│     error: str | None = None                                                                                                                                │
│                                                                                                                                                             │
│ # Finding gains:                                                                                                                                            │
│ class Finding(BaseModel):                                                                                                                                   │
│     # ... existing fields ...                                                                                                                               │
│     source_persona: str | list[str] | None = None  # NEW                                                                                                    │
│                                                                                                                                                             │
│ # ReviewBundle gains:                                                                                                                                       │
│ class ReviewBundle(BaseModel):                                                                                                                              │
│     # ... existing fields ...                                                                                                                               │
│     review_mode: ReviewMode = ReviewMode.AUTO  # NEW                                                                                                        │
│     personas: list[str] | None = None          # NEW                                                                                                        │
│     project_rules: str | None = None           # NEW                                                                                                        │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Files to Create/Modify                                                                                                                                      │
│                                                                                                                                                             │
│ ┌────────┬───────────────────────────────────┬──────────────────────────────────────────────────────────────────────────┐                                   │
│ │ Action │               File                │                                 Purpose                                  │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/model_tiers.py             │ Built-in TIER_MAP + pick_best() resolver                                 │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/review_orchestrator.py     │ Pipeline: classify → dispatch → judge → return                           │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/review_classifier.py       │ LLM classifier for auto mode                                             │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/review_judge.py            │ LLM judge for synthesis                                                  │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/agents/__init__.py         │ AgentConfig, AgentRegistry                                               │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/agents/correctness.py      │ Agent prompt + checklist                                                 │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/agents/security.py         │ Agent prompt + checklist                                                 │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/agents/design.py           │ Agent prompt + checklist                                                 │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/agents/tests.py            │ Agent prompt + checklist                                                 │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ server/agents/architecture.py     │ Agent prompt + checklist                                                 │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ MODIFY │ server/models.py                  │ ReviewMode, source_persona, AgentResult, bundle fields                   │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ MODIFY │ server/mcp_server.py              │ Add params, route to orchestrator                                        │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ MODIFY │ server/review_engine.py           │ Add create_session_from_findings()                                       │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ MODIFY │ server/prompts.py                 │ Add project_rules to build_review_context()                              │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ MODIFY │ docker-compose.yml                │ New env vars (CLASSIFIER_MODEL, AGENT_MODEL, JUDGE_MODEL, AGENT_TIMEOUT) │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ tests/test_review_orchestrator.py │ Orchestrator unit tests                                                  │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ tests/test_review_classifier.py   │ Classifier unit tests                                                    │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ NEW    │ tests/test_review_judge.py        │ Judge unit tests                                                         │                                   │
│ ├────────┼───────────────────────────────────┼──────────────────────────────────────────────────────────────────────────┤                                   │
│ │ MODIFY │ tests/test_review_engine.py       │ Tests for create_session_from_findings()                                 │                                   │
│ └────────┴───────────────────────────────────┴──────────────────────────────────────────────────────────────────────────┘                                   │
│                                                                                                                                                             │
│ ---                                                                                                                                                         │
│ Verification                                                                                                                                                │
│                                                                                                                                                             │
│ Unit Tests                                                                                                                                                  │
│                                                                                                                                                             │
│ pytest tests/test_review_classifier.py    # Classifier routes correctly per mode                                                                            │
│ pytest tests/test_review_orchestrator.py  # Full pipeline: classify→dispatch→judge                                                                          │
│ pytest tests/test_review_judge.py         # Dedup, severity reconciliation, guardrails                                                                      │
│ pytest tests/test_review_engine.py        # create_session_from_findings + existing tests pass                                                              │
│                                                                                                                                                             │
│ Integration Tests                                                                                                                                           │
│                                                                                                                                                             │
│ # Standard mode: exact same behavior as before (regression check)                                                                                           │
│ # Auto mode: classifier selects agents, findings returned with source_persona                                                                               │
│ # Thorough mode: all 5 agents run, judge synthesizes                                                                                                        │
│ # Focused mode: only specified agents run                                                                                                                   │
│ # Partial failure: one agent times out, others' findings still returned                                                                                     │
│ # project_rules: architecture agent references project rules in findings                                                                                    │
│                                                                                                                                                             │
│ Manual MCP Verification                                                                                                                                     │
│                                                                                                                                                             │
│ docker compose up -d                                                                                                                                        │
│ # Call start_review via MCP with review_mode="auto" and project_rules="..."                                                                                 │
│ # Verify: classifier rationale in get_review_summary                                                                                                        │
│ # Verify: findings have source_persona populated                                                                                                            │
│ # Verify: no duplicate findings across agents                                                                                                               │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
