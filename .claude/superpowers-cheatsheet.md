# Superpowers Plugin Cheat Sheet

**Plugin:** superpowers v5.0.2
**Author:** Jesse Vincent
**Installed:** `~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.2/`

---

## Skills (invoke as `/skill-name` or triggered automatically)

### Planning & Design

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `/brainstorm` | Before ANY creative work — features, components, behavior changes | Explores intent, requirements, and design through dialogue before implementation |
| `/write-plan` | When you have a spec/requirements for a multi-step task | Writes implementation plans as bite-sized tasks assuming zero codebase context |
| `/execute-plan` | When you have a written plan to execute | Loads plan, reviews critically, executes tasks with review checkpoints |

### Development Workflow

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `/test-driven-development` | Before implementing any feature or bugfix | RED-GREEN-REFACTOR: write failing test, watch it fail, write minimal code to pass, refactor |
| `/systematic-debugging` | When hitting any bug, test failure, or unexpected behavior | Investigates root cause (errors, reproduce, changes, evidence) before proposing fixes |
| `/subagent-driven-development` | Executing plans with independent tasks | Dispatches fresh subagent per task with two-stage review (spec then code quality) |
| `/dispatching-parallel-agents` | 2+ independent tasks without shared state | Delegates to specialized agents with isolated context for parallel work |
| `/using-git-worktrees` | Starting feature work that needs isolation | Creates isolated git worktrees with smart directory selection |

### Review & Quality

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `/requesting-code-review` | After completing tasks or major features | Dispatches code-reviewer subagent to catch issues before merge |
| `/receiving-code-review` | Before implementing review feedback | Evaluates feedback technically — requires rigor, not blind agreement |
| `/verification-before-completion` | Before claiming work is done | Runs verification commands and confirms output — evidence before assertions |
| `/simplify` | After writing code | Reviews changed code for reuse, quality, and efficiency, then fixes issues |

### Completion

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `/finishing-a-development-branch` | Implementation complete, tests pass | Presents structured options: merge, PR, keep, or discard — then executes choice |

### Meta

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `/writing-skills` | Creating or editing skills | TDD for process docs — write failing test, verify, refactor |
| `/using-superpowers` | Session start (automatic) | Establishes how to find and use skills |

---

## Agent

| Agent | When it runs | What it does |
|-------|-------------|--------------|
| `code-reviewer` | After completing a major project step or plan task | Reviews implementation against plan and coding standards, identifies deviations, provides actionable recommendations |

---

## Hook

| Hook | Trigger | What it does |
|------|---------|--------------|
| `session-start` | On startup, resume, clear, or compact | Initializes superpowers context at session start |

---

## Typical Workflow

```
1. /brainstorm          — explore what to build
2. /write-plan          — create implementation plan
3. /execute-plan        — execute with checkpoints
   └─ /test-driven-development  — for each task
   └─ /systematic-debugging     — if something breaks
   └─ /verification-before-completion — before marking done
4. /requesting-code-review      — review the work
5. /receiving-code-review       — handle feedback
6. /finishing-a-development-branch — merge/PR/cleanup
```

---

## Other Built-in Skills (not from superpowers)

| Skill | What it does |
|-------|--------------|
| `/loop 5m /command` | Runs a slash command on a recurring interval (default 10m) |
| `/keybindings-help` | Customize keyboard shortcuts and keybindings |
| `/claude-api` | Help building apps with Claude API / Anthropic SDK |
