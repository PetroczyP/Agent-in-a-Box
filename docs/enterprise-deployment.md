# Enterprise Deployment Guide

How to deploy Agent-in-a-Box in enterprise CI/CD pipelines on Azure, with GitHub Actions, Azure DevOps, or GitLab CI.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Azure VNet                                                  │
│                                                              │
│  ┌───────────────┐       ┌─────────────────────┐            │
│  │ CI Runner     │──HTTP─▶│ Agent-in-a-Box      │            │
│  │ (self-hosted) │◀──────│ (Container Apps /   │            │
│  │               │       │  ACI / AKS)         │            │
│  └───────────────┘       └─────────┬───────────┘            │
│                                    │                         │
│              ┌─────────────────────┼─────────────────┐      │
│              ▼                     ▼                  ▼      │
│  ┌────────────────┐   ┌───────────────┐   ┌──────────────┐ │
│  │ Azure OpenAI   │   │ Azure         │   │ Azure        │ │
│  │ (private       │   │ Key Vault     │   │ Container    │ │
│  │  endpoint)     │   │               │   │ Registry     │ │
│  └────────────────┘   └───────────────┘   └──────────────┘ │
│                                                              │
│  ─── Azure Firewall (FQDN rules for external APIs) ───     │
│              │                     │                         │
└──────────────┼─────────────────────┼─────────────────────────┘
               ▼                     ▼
        api.anthropic.com     *.githubcopilot.com
```

Agent-in-a-Box runs as a stateless container. CI pipelines call it via the REST API (`POST /api/v1/reviews`) or MCP stdio (`docker exec`). The container makes outbound HTTPS calls to whichever AI model backend is configured.

## Where to Host the Container

| Azure Service | Best For | Notes |
|---------------|----------|-------|
| **Azure Container Apps** | Most enterprises. Serverless, scales to zero, VNet support. | Recommended. No K8s expertise needed. You are not billed when scaled to zero. |
| **Azure Container Instances (ACI)** | Simple, ad-hoc runs. CI-triggered one-shot containers. | No orchestration. Pay per second. |
| **Azure Kubernetes Service (AKS)** | Large-scale fleets or complex multi-service setups. | Full K8s control, higher operational overhead. |

**Azure Container Apps** supports full VNet integration (deploy into a dedicated subnet), NAT Gateway for static outbound IPs, and UDR routing through Azure Firewall.

## Firewall Rules

All rules are **outbound HTTPS, port 443/TCP**. Agent-in-a-Box requires no inbound connections from the internet.

### AI Model Backend Endpoints

Only whitelist the backend(s) you are using.

**GitHub Copilot** (full allowlist from [GitHub docs](https://docs.github.com/en/copilot/managing-copilot/managing-github-copilot-in-your-organization/configuring-your-proxy-server-or-firewall-for-copilot)):

| FQDN | Purpose |
|------|---------|
| `github.com/login/*` | Authentication |
| `api.github.com/user` | User validation |
| `api.github.com/copilot_internal/*` | Copilot API |
| `copilot-proxy.githubusercontent.com` | Inference proxy |
| `copilot-telemetry.githubusercontent.com/telemetry` | Telemetry |
| `*.githubcopilot.com/*` | Copilot service |
| `*.individual.githubcopilot.com` | Individual plan |
| `*.business.githubcopilot.com` | Business plan |
| `*.enterprise.githubcopilot.com` | Enterprise plan |
| `default.exp-tas.com` | Experimentation service |
| `collector.github.com/*` | Metrics collection |
| `origin-tracker.githubusercontent.com` | Origin tracking |

**Anthropic API** ([docs](https://platform.claude.com/docs/en/api/ip-addresses)):

| FQDN / IP Range | Purpose |
|------------------|---------|
| `api.anthropic.com` | Primary API endpoint |
| `160.79.104.0/23` (inbound IPv4) | Static IP range (for IP-based rules) |
| `160.79.104.0/21` (outbound IPv4) | Static IP range |

Anthropic publishes fixed IP addresses that will not change without notice — IP-based firewall rules are viable.

**OpenAI API:**

| FQDN | Purpose |
|------|---------|
| `api.openai.com` | Primary API endpoint |

OpenAI uses Cloudflare CDN with dynamic IPs — use FQDN-based rules only (no stable IP ranges). If your firewall does SSL inspection, exempt `api.openai.com` to avoid certificate errors.

**Azure OpenAI (private endpoint):**

No internet-facing firewall rules needed. Traffic stays within the Azure VNet via Private Link. Requires:
- Private DNS Zone for `privatelink.openai.azure.com`
- Custom subdomain on the Azure OpenAI resource
- Disable public network access on the resource

**Ollama (local):**

No firewall rules. Fully offline. Container-to-container networking only (e.g., `http://ollama:11434`).

### NSG vs Azure Firewall

Azure Network Security Groups (NSGs) support **IP-based rules only** — they cannot filter by FQDN. For domain-based outbound filtering (needed for Copilot and OpenAI), use **Azure Firewall** with application rules. Most enterprises already have Azure Firewall in their hub VNet.

Anthropic is the exception: their static IP ranges allow NSG-only rules if that backend is the only external dependency.

## CI/CD Integration

### GitHub Actions

GitHub Actions supports **service containers** via the `services:` keyword. The Agent-in-a-Box container runs alongside your job and is accessible via HTTP.

**Example workflow (self-hosted runner in VNet):**

```yaml
name: Code Review
on: [pull_request]

jobs:
  review:
    runs-on: self-hosted  # runner in your Azure VNet
    services:
      reviewer:
        image: your-acr.azurecr.io/agent-in-a-box:latest
        credentials:
          username: ${{ secrets.ACR_USERNAME }}
          password: ${{ secrets.ACR_PASSWORD }}
        ports:
          - 8080:8080
        env:
          GITHUB_TOKEN: ${{ secrets.COPILOT_PAT }}
    steps:
      - uses: actions/checkout@v4

      - name: Submit review
        run: |
          # Generate diff
          DIFF=$(git diff origin/main...HEAD)

          # Call Agent-in-a-Box REST API
          curl -s -X POST http://localhost:8080/api/v1/reviews \
            -H "Content-Type: application/json" \
            -d "{\"diff\": $(echo "$DIFF" | jq -Rs .)}" \
            -o findings.json

      - name: Post findings as PR comment
        run: |
          # Parse findings and post to PR
          # (implementation depends on your preferred format)
```

**Requirements:**
- Service containers require **Linux runners**
- Self-hosted runners must have Docker installed
- Self-hosted runners in a VNet need outbound HTTPS to `github.com`, `api.github.com`, `*.actions.githubusercontent.com`, `codeload.github.com`, and `*.blob.core.windows.net`

**GitHub-hosted runners** have full internet access but cannot reach your VNet-internal services. Use self-hosted runners for private deployments.

### Azure DevOps Pipelines

**Self-hosted agent in VNet (recommended):**

```yaml
trigger:
  - main

pool:
  name: 'MyPrivatePool'  # self-hosted agent pool in VNet

steps:
  - script: |
      docker run -d --name reviewer \
        -p 8080:8080 \
        -e GITHUB_TOKEN=$(COPILOT_PAT) \
        your-acr.azurecr.io/agent-in-a-box:latest
    displayName: 'Start Agent-in-a-Box'

  - script: |
      DIFF=$(git diff origin/main...HEAD)
      curl -s -X POST http://localhost:8080/api/v1/reviews \
        -H "Content-Type: application/json" \
        -d "{\"diff\": $(echo "$DIFF" | jq -Rs .)}"
    displayName: 'Submit code review'

  - script: docker stop reviewer && docker rm reviewer
    displayName: 'Cleanup'
    condition: always()
```

**Container jobs** (alternative — runs the entire job inside the Agent-in-a-Box image):

```yaml
pool:
  name: 'MyPrivatePool'

container:
  image: your-acr.azurecr.io/agent-in-a-box:latest

steps:
  - script: python -m server.review_cli --diff "$(git diff)"
    displayName: 'Run review'
```

**ADO agent outbound requirements** (port 443): `dev.azure.com`, `*.dev.azure.com`, `*.visualstudio.com`, `vstsagentpackage.azureedge.net`, `*.blob.core.windows.net`, `mcr.microsoft.com`.

### GitLab CI/CD

**GitLab Runner with Docker executor:**

```yaml
code-review:
  image: alpine:latest
  services:
    - name: your-acr.azurecr.io/agent-in-a-box:latest
      alias: reviewer
  variables:
    GITHUB_TOKEN: $COPILOT_PAT
    FF_NETWORK_PER_BUILD: "true"  # isolated network per job
  script:
    - apk add --no-cache curl jq git
    - DIFF=$(git diff origin/main...HEAD)
    - |
      curl -s -X POST http://reviewer:8080/api/v1/reviews \
        -H "Content-Type: application/json" \
        -d "{\"diff\": $(echo "$DIFF" | jq -Rs .)}"
```

With `FF_NETWORK_PER_BUILD`, service containers are reachable by their alias hostname (`reviewer`). Without it, use Docker's legacy linking.

## Secrets Management

Never store API keys in pipeline YAML, environment variables, or container configs. Use your platform's secrets integration with Azure Key Vault.

### GitHub Actions

Store secrets in **Settings > Secrets and variables > Actions**. For Key Vault integration, use the [Azure Login action](https://github.com/azure/login) with OIDC federation:

```yaml
- uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

- uses: azure/get-keyvault-secrets@v1
  with:
    keyvault: 'my-keyvault'
    secrets: 'copilot-pat, anthropic-key'
  id: kv-secrets
```

### Azure DevOps

Link a **variable group** to Azure Key Vault ([docs](https://learn.microsoft.com/en-us/azure/devops/pipelines/library/link-variable-groups-to-key-vaults)). Pipelines fetch the latest secret values at runtime — only secret names are stored in ADO, not values.

**Caveat:** Key Vaults behind private endpoints are not supported with RBAC mode (ADO is not an Azure trusted service). Use Vault access policy mode if the Key Vault has a private endpoint.

### GitLab CI

Use **OIDC federation** with Azure AD ([docs](https://docs.gitlab.com/ci/cloud_services/azure/)). GitLab exchanges its OIDC token for temporary Azure AD credentials — no long-lived secrets stored in GitLab. The Azure AD service principal then accesses Key Vault via standard RBAC.

### Azure Container Apps (Direct Hosting)

Use **managed identity** with Key Vault references ([docs](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets)). The Container App fetches secrets at runtime using its identity — zero credentials in the container configuration. Secrets auto-rotate within 30 minutes when new Key Vault versions appear.

## Container Image Distribution

| Approach | How | Best For |
|----------|-----|----------|
| **GitHub Container Registry** | We publish to `ghcr.io`. Enterprise pulls and mirrors. | Public distribution. |
| **Azure Container Registry** | Mirror from GHCR using [ACR Artifact Cache](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-artifact-cache), or build from source. | Azure-native enterprises. |
| **Build from source** | Clone repo, `docker build`, push to private registry. | Air-gapped environments, maximum control. |

ACR Artifact Cache creates a local copy on first pull and serves subsequent pulls from cache. Supports GHCR (authenticated and unauthenticated) and Docker Hub (authenticated only). Maximum 1,000 cache rules per registry.

For air-gapped environments, build from source on an internet-connected machine, push to a portable registry or `docker save` to a tarball, and transfer to the isolated network.

## Air-Gapped / Zero-Internet Deployment

For regulated industries (finance, defense, government) that cannot allow outbound internet from workloads:

| Backend | Internet Required | How |
|---------|-------------------|-----|
| **Azure OpenAI** | No | Private endpoint in VNet. Traffic stays on Azure backbone. All models in your region are available. |
| **Ollama** | No | Import pre-downloaded GGUF model files via `ollama create`. Zero network calls. GPU strongly recommended. |
| **Hybrid** | No | Ollama for fast triage, Azure OpenAI for deep review. All VNet-internal. |

**Ollama air-gapped setup:**
1. On an internet-connected machine, download model weights as GGUF files (e.g., from HuggingFace).
2. Transfer GGUF files to the air-gapped host via secure file transfer.
3. Create a Modelfile: `FROM /path/to/model.gguf`
4. Run `ollama create my-model` to register locally.
5. Agent-in-a-Box connects to `http://ollama:11434` via container networking.

## Enterprise Gateway Pattern (Optional)

For organizations that want centralized control over AI API usage, deploy **Azure API Management** as an AI gateway ([reference architecture](https://learn.microsoft.com/en-us/ai/playbook/solutions/genai-gateway/reference-architectures/apim-based)):

```
Agent-in-a-Box  ──▶  APIM (internal VNet)  ──▶  Azure OpenAI (private endpoint)
                                             ──▶  Anthropic (via Azure Firewall)
                                             ──▶  OpenAI (via Azure Firewall)
```

APIM provides:
- **Rate limiting** — tokens-per-minute (TPM) and requests-per-minute (RPM) per team/project
- **Token quota management** — hourly, daily, weekly, monthly budgets
- **Load balancing** — round-robin, weighted, or priority-based across backends
- **Failover** — circuit breaker with dynamic retry using backend `Retry-After` headers
- **Audit logging** — full request/response logging for compliance
- **Single endpoint** — Agent-in-a-Box calls one internal URL; APIM routes to the right backend

APIM VNet injection is available in Developer, Premium (Classic), and Premium v2 tiers.

## Summary: What to Whitelist

Minimal outbound rules for a self-hosted CI runner + Agent-in-a-Box in an Azure VNet:

| Destination | Port | Purpose | Required? |
|-------------|------|---------|-----------|
| CI platform endpoints (see per-platform sections above) | 443 | Runner ↔ CI service communication | Always |
| Your ACR (`*.azurecr.io`) | 443 | Pull container images | Always |
| Your Key Vault (`*.vault.azure.net`) | 443 | Fetch secrets | Always |
| `login.microsoftonline.com` | 443 | Azure AD authentication | Always |
| AI backend endpoints (see per-backend sections above) | 443 | Model inference calls | Only for non-private-endpoint backends |

If using **only** Azure OpenAI with a private endpoint and Ollama, the container needs **zero outbound internet access**. All traffic stays within the VNet.
