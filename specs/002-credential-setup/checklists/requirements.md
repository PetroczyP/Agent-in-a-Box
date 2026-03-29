# Requirements Quality Checklist — 002-credential-setup

## Spec Structure

- [x] All mandatory sections present (User Scenarios, Requirements, Success Criteria)
- [x] User stories prioritized (P1, P2, P3)
- [x] Each user story independently testable
- [x] Each user story has acceptance scenarios in Given/When/Then format
- [x] Edge cases section populated with concrete behaviors (not open questions)

## Requirements Quality

- [x] All FRs use MUST/SHOULD/MAY language correctly
- [x] All FRs are testable with concrete pass/fail criteria
- [x] No implementation details leak into FRs (technology-agnostic where possible)
  - Note: FR-001 names Fernet and FR-002 names Docker secret path — these are constrained by the constitution's tech stack, not premature implementation decisions
- [x] FR-003: Enumerates all rejected token prefixes (`ghp_`, `gho_`, `ghs_`, `ghu_`)
- [x] FR-005: Specifies the exact validation method (`list_models()`) and 4 distinct failure modes (format error, auth error, permission error, SDK error). Permission error broadened to "cannot access Copilot" per coordinator decision. All messages must be verbose with URLs and remediation steps.
- [x] FR-006: Specifies masking format (`github_pat_...XXXX`)
- [x] FR-007: Covers logs, API responses, web UI, and error messages
- [x] FR-008: Specifies the exact port binding format
- [x] FR-009: Credential status page at `/` — shows source + masked token only, no connection status claims
- [x] FR-010: MCP freshness boundary — resolved at process startup, rotation effective on next connection

## Success Criteria

- [x] All SCs are measurable
- [x] SC-001: Time-based (under 2 minutes)
- [x] SC-002: Behavioral (no restart, next MCP connection uses new token, active sessions keep their token)
- [x] SC-003: Verifiable (grep-based check)
- [x] SC-004: Combinatorial (all 4 source combinations)
- [x] SC-005: Qualitative but testable (specific error messages for each rejection type)

## Constitution Compliance

- [x] No hardcoded repo knowledge (project-agnostic)
- [x] No host volume mounts (Docker named volume only)
- [x] Security boundary maintained (only GitHub PAT enters container)
- [x] TDD compatible (all requirements have testable pass/fail criteria)
- [x] YAGNI: no external KMS, no RBAC, no multi-user

## Remaining Risks

- Copilot SDK (`github-copilot-sdk>=0.1.0`) is Technical Preview — `list_models()` API may change. Mitigation: document assumption, design fallback path in design phase.
- Docker Compose secrets without Swarm are file mounts with no Docker-level encryption. Mitigation: Fernet layer provides at-rest encryption; this is documented in the spec rationale.
