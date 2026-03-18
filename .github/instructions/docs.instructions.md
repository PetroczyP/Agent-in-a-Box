---
applyTo: "docs/**/*.md"
---

# Documentation Conventions

## Accuracy Requirements

- All file path references must point to paths that actually exist in the repo. The spec directory structure is `specs/NNN-feature-name/` with `spec.md`, `plan.md`, `tasks.md`, etc.
- Contract references use full paths: `specs/001-ai-code-reviewer/contracts/review-engine.md`, not shortened forms.
- Architecture diagrams must reflect the CURRENT transport mechanism (MCP stdio via `docker exec`), not planned features. The REST API transport (spec 011) is NOT implemented.

## Firewall / Network Tables

- Enterprise firewall tables must use **FQDN/hostname only**, not URL paths. Most firewalls (including Azure Firewall) match on hostname, not path.
- Move path information to the Purpose column as informational context.
- Example: `github.com` with Purpose "Authentication (`/login/*`)" — NOT `github.com/login/*` in the FQDN column.

## CI/CD Examples

- GitHub Actions checkout steps must include `fetch-depth: 0` when the workflow uses `git diff` against a base branch. Shallow clones (the default) lack `origin/main`.
- Example commands must be tested or clearly marked as illustrative.
- Docker commands should reference named containers consistently.

## Cross-References

- Spec references: `spec NNN` or `specs/NNN-feature-name/spec.md`
- Feature status must match the spec roadmap in CLAUDE.md and README.md
- When referencing planned features, clearly mark them as "planned" or "not yet implemented"
