# Web Routes Contract: Credential Setup (002)

## Module: `server/web_routes.py`

FastAPI routes for credential management web UI (setup wizard, settings, status page).

## Routes

### GET `/` — Credential Status Page (FR-009)

**Behavior**:
- If no credential is configured (resolver returns `None`): redirect to `/setup`
- Otherwise: render status page showing source + masked token

**Template**: `templates/status.html`

**Context**:
```python
{
    "source": "docker_secret" | "env_var" | "stored",
    "masked_token": "github_pat_...XXXX",  # prefix + last 4 chars
    "message": str | None,  # flash message from query param ?msg=
}
```

**Note**: Page MUST NOT claim connection status or validity (FR-009).

---

### GET `/setup` — Setup Wizard (FR-004)

**Behavior**:
- If a credential is already configured: redirect to `/`
- Otherwise: render setup wizard with PAT creation instructions

**Template**: `templates/setup.html`

**Context**:
```python
{
    "error": str | None,  # validation error message from failed POST
}
```

---

### POST `/setup` — Submit Token (FR-004, FR-005)

**Behavior**:
1. Read `token` from form body
2. Call `TokenValidator.validate(token)` — format + Copilot access
3. On success: `CredentialStore.store(token)`, redirect to `/?msg=saved`
4. On failure: re-render `/setup` with error message from `TokenValidationError`

**Form field**: `token` (text input)

**PRG pattern**: POST validates + stores, then redirects (GET) to status page.

---

### GET `/settings` — Settings Page (FR-006)

**Behavior**:
- Show masked current token and credential source
- If source is `stored`: show change form
- If source is `docker_secret` or `env_var`: disable form, show explanation

**Template**: `templates/settings.html`

**Context**:
```python
{
    "source": CredentialSource,
    "masked_token": str | None,
    "can_rotate": bool,  # True only when source is "stored"
    "message": str | None,
    "error": str | None,
}
```

---

### POST `/settings/rotate` — Rotate Token (FR-006)

**Behavior**:
1. Check source is `stored` — reject if externally managed
2. Read `token` from form body
3. Call `TokenValidator.validate(token)`
4. On success: `CredentialStore.store(token)` (replaces old), redirect to `/settings?msg=rotated`
5. On failure: re-render `/settings` with error message, old token preserved

---

## Shared Helpers

```python
def mask_token(token: str) -> str:
    """Mask token for display: 'github_pat_...XXXX' (prefix + last 4 chars).

    Returns empty string for None/empty input.
    """
```

## Templates

All templates extend `templates/base.html` (monospace dark theme, single CSS).

| Template | Route | Purpose |
|----------|-------|---------|
| `base.html` | — | Layout: nav, flash messages, footer |
| `status.html` | `GET /` | Source + masked token display |
| `setup.html` | `GET /setup` | PAT instructions + token input form |
| `settings.html` | `GET /settings` | Masked token + rotation form |

## Flash Messages

Via query parameter `?msg=` (not session-based, per R-5 YAGNI decision):
- `saved` → "Token saved successfully."
- `rotated` → "Token rotated successfully."

## Dependencies

- `CredentialResolver` — resolve current credential source
- `CredentialStore` — store/load credentials
- `TokenValidator` — validate tokens before storing
- `FastAPI`, `Jinja2Templates`, `Request`, `Form`
