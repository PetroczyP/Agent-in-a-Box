# Research — 002-credential-setup

## R-1: Fernet Encryption for Credential Storage

**Decision**: Use `cryptography.fernet.Fernet` for at-rest encryption of stored PATs.

**Rationale**: Fernet provides authenticated symmetric encryption (AES-128-CBC + HMAC-SHA256). It is the standard Python approach for encrypting sensitive data at rest. The `cryptography` library is actively maintained and widely used. The key is a 44-char URL-safe base64 string generated via `Fernet.generate_key()`.

**Alternatives considered**:
- AES-256-GCM via `cryptography.hazmat` — more flexible but more complex; Fernet's higher-level API is sufficient and less error-prone
- `nacl.secret.SecretBox` (PyNaCl) — good library but adds a dependency; `cryptography` is already transitively available in many Python environments
- External KMS (AWS KMS, HashiCorp Vault) — rejected per YAGNI constitution principle

**Source**: [cryptography.io Fernet docs](https://cryptography.io/en/latest/fernet/)

## R-2: Docker Secrets in Compose (Non-Swarm)

**Decision**: Support Docker secrets via `file:` source in `docker-compose.yml`, mounted at `/run/secrets/github_token`.

**Rationale**: Docker Compose (without Swarm) supports secrets as file mounts. No Docker-level encryption — the secret file is bind-mounted into the container. This is acceptable because: (1) our Fernet layer handles at-rest encryption for stored credentials, (2) Docker secrets still provide better hygiene than env vars by avoiding exposure through `/proc/*/environ`, crash dumps, and subprocess inheritance.

**Alternatives considered**:
- Docker Swarm secrets — real encryption but requires Swarm mode, which is not in scope
- SOPS/age encrypted files — adds tooling complexity for limited benefit in single-user context

**Source**: [Docker Compose secrets docs](https://docs.docker.com/compose/how-tos/use-secrets/)

## R-3: Fine-Grained PAT Prefix Validation

**Decision**: Validate token format by checking the `github_pat_` prefix. Reject `ghp_`, `gho_`, `ghs_`, `ghu_`.

**Rationale**: GitHub uses distinct prefixes for each token type. Fine-grained PATs are 93 characters with the `github_pat_` prefix. Classic PATs use `ghp_` (40 chars after prefix). This is a well-documented pattern used by other tools (GitGuardian, GitHub's own token scanning).

**Alternatives considered**:
- Regex validation — overkill; prefix check is sufficient and simpler
- GitHub API call to introspect token type — adds network latency and doesn't help with format validation

**Source**: [GitHub token prefixes](https://gist.github.com/magnetikonline/073afe7909ffdd6f10ef06a00bc3bc88), [GitHub blog on fine-grained PATs](https://github.blog/security/application-security/introducing-fine-grained-personal-access-tokens-for-github/)

## R-4: Copilot SDK Error Classification (Design-Phase Spike)

**Decision**: Use two-step validation (GitHub API + Copilot SDK) to produce the 4 distinct error types required by FR-005.

**Findings**: The existing `CopilotReviewClient._init_sdk()` in `server/copilot_client.py:199-225` classifies errors by checking `str(e).lower()` for `"auth"`, `"401"`, or `"403"`. Both expired tokens and permission-denied errors produce `CopilotAuthError`. The Copilot service uses HTTP 403 for multiple failure modes (expired tokens, missing permissions, missing subscription), making the status code unreliable for distinguishing auth from permission errors at the SDK level alone.

**Design consequence**: FR-005 requires 4 distinct error messages. The Copilot SDK alone cannot distinguish auth from permission errors. We achieve best-effort distinction by adding a preliminary GitHub API check, with an honest confidence model:

1. **Format error** — prefix check (local, no SDK needed)
2. **Auth error** — `GET https://api.github.com/user` returns HTTP 401 → token is expired, revoked, or invalid. Only 401 maps to auth — other non-2xx responses (403 rate limit, 5xx server error) are treated as inconclusive and do NOT produce an auth classification.
3. **Permission error** — GitHub API check confirmed auth (returned 2xx) AND `list_models()` fails → token authenticates to GitHub but cannot access Copilot. Message covers the most common causes: missing `copilot_requests` permission, no active Copilot subscription, or enterprise policy restriction.
4. **SDK error** — `ImportError` or `CopilotUnavailableError` (SDK not installed / CLI won't start)
5. **Inconclusive fallback** — If `GET /user` returned non-401 non-2xx (inconclusive) AND `list_models()` also fails, we cannot reliably distinguish auth from permission. In this case, `error_type="auth"` with a combined message covering both possibilities. This is honest — we don't overclaim.

**Validation sequence**: format check → GitHub API auth probe → Copilot SDK access check. The GitHub API probe is diagnostic only (used for error classification), not a gate. If the probe is inconclusive, the Copilot check still runs.

**Confidence model**:
| GET /user result | list_models() result | Classification | Confidence |
|-----------------|---------------------|----------------|------------|
| 401 | (not called) | auth | High — 401 is definitive |
| 2xx | fails (CopilotAuthError) | permission | High — token works for GitHub but not Copilot |
| 2xx | fails (CopilotUnavailableError) | sdk | High — SDK problem, not token |
| non-401 non-2xx | fails (CopilotAuthError) | auth (combined msg) | Low — cannot distinguish, honest fallback |
| any | succeeds | (validation passes) | — |

**Note on FR-005**: The spec says "Generic GitHub API validation (GET /user) is insufficient." Correct — GET /user is insufficient as the *sole* validation. It is used here as a *diagnostic probe* to disambiguate the error type, not as a replacement for the Copilot SDK check.

**Coordinator decision (design round 4)**: Peter chose Option A — broaden FR-005's "permission error" from "specifically missing copilot_requests" to "cannot access Copilot" with verbose, diagnostic-style messages. All error messages must be chatty: list possible causes and include specific URLs (github.com/settings/tokens, github.com/settings/copilot) so users can self-diagnose. The 4-type taxonomy (format, auth, permission, sdk) is preserved.

**Source**: [GitHub REST API — Get the authenticated user](https://docs.github.com/en/rest/users/users#get-the-authenticated-user). Returns 200 for valid tokens, 401 for expired/revoked, 403 for certain rate-limit or policy scenarios. The Copilot SDK uses 403 for multiple failure modes — see [community discussions](https://github.com/orgs/community/discussions/165646).

## R-5: FastAPI + Jinja2 Web UI Patterns

**Decision**: Use FastAPI's `Jinja2Templates` with `StaticFiles` mount. Server-rendered HTML forms with POST redirects (PRG pattern).

**Rationale**: Constitution requires Jinja2, no React/SPA. FastAPI has built-in support for both. The PRG (Post/Redirect/Get) pattern prevents form resubmission on refresh. Flash messages via query parameters (simpler than session-based flash, aligns with YAGNI).

**Alternatives considered**:
- HTMX for partial page updates — adds a JS dependency; not needed for 3 simple pages
- Session-based flash messages — requires session middleware; query params are simpler
