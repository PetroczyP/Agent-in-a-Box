# Feature Specification: AgentinaBox — Slack Integration

**Feature Branch**: `009-slack-integration`
**Created**: 2026-03-16
**Status**: Backlog (Draft)
**Depends on**: 001-ai-code-reviewer, 002-credential-setup

## Summary

Enable users to interact with AgentinaBox through Slack — submit code for review, receive findings, and discuss results without leaving their team's communication tool. This positions AgentinaBox as accessible to non-developers (tech leads, PMs reviewing PRs) and enables team-based review workflows.

## Context & Research

Slack's official MCP server is GA (February 2026) and provides tools for messaging, search, channels, and user profiles. Two integration patterns exist:

1. **Slack as delivery channel**: A Slack bot receives review requests (e.g., a GitHub PR URL or pasted code), dispatches to an AgentinaBox container, and posts structured findings back to the channel/thread.
2. **Slack MCP as a tool for the agent**: The agent inside the container connects to Slack's MCP server to post results, read context from channels, or interact with users.

Pattern 1 is simpler and more aligned with our architecture (the container is a stateless worker — Slack is an orchestrator, not a tool inside the container).

## Open Questions

- Should the Slack bot run as a separate service that orchestrates AgentinaBox containers, or should Slack connectivity live inside the container itself?
- How does authentication work? The bot needs a Slack app token + the user needs to authorize. Plus the container still needs its model API key.
- Should findings be posted as Slack messages, or as structured Block Kit cards with severity colors?
- How do we handle code snippets in Slack (character limits, formatting)?
- Should we support `/review <github-pr-url>` slash commands?
- Do we need to handle Slack's rate limits for large reviews with many findings?

## Rough User Stories

### US1 - Submit PR for Review via Slack (P1)

A tech lead pastes a GitHub PR URL in a Slack channel where the AgentinaBox bot is present. The bot extracts the diff, sends it to an AgentinaBox container for review, and posts the findings back as a threaded reply with severity-colored cards.

### US2 - Discuss Findings in Thread (P2)

After receiving findings, a developer replies in the Slack thread to ask about a specific finding. The bot routes the message to the container's `discuss` tool and posts the response back.

### US3 - Review Summary on Demand (P3)

A user reacts with a specific emoji (e.g., :memo:) or types `/review-summary` to get a summary of the current review session posted to the channel.

## Dependencies

- Spec 001 (Core Review Server) — must be stable
- Spec 002 (Credential Setup) — Slack app tokens need to be managed alongside model API keys
- A Slack app registered in the target workspace

## Technical Notes

- Slack's official MCP server: `https://mcp.slack.com/mcp` (Streamable HTTP, OAuth 2.0)
- Community alternative: `tuannvm/slack-mcp-client` (Go, Socket Mode, Docker/K8s deployable)
- Slack Block Kit for rich message formatting
- Consider: the Slack bot could be a separate lightweight container that orchestrates AgentinaBox containers
