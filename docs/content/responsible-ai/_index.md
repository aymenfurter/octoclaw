---
title: "Security, Governance & Responsible AI"
weight: 25
---

Polyclaw is in **early preview**. Hardening the security posture is the next major focus area for the project. If you choose to run Polyclaw today, treat it as experimental software and read this page carefully.

---

## Understand the Risks

Polyclaw is an autonomous agent. That means it can act without asking you first -- sending messages, writing files, executing code, making API calls, and even placing phone calls on your behalf. This is powerful, but it comes with real consequences if something goes wrong.

**What can go wrong:**

- **Unintended actions.** The agent decides what tools to call based on its prompt and conversation context. A misunderstood instruction can lead to unwanted commits, messages sent to the wrong person, or files overwritten.
- **Credential exposure.** Polyclaw operates under your identity. Your GitHub token, Azure credentials, and API keys are available to the agent. A prompt injection attack or a badly written skill could exfiltrate or misuse them.
- **Cost overruns.** The agent can spin up Azure resources, make API calls, and schedule recurring tasks. Without monitoring, a runaway loop could generate unexpected cloud bills.
- **Code execution.** The agent can execute arbitrary code on your machine (or in a sandbox). Generated code is not reviewed by a human before execution by default.
- **Data leakage.** Conversations, files, and tool outputs pass through the Copilot SDK and any configured channels. Sensitive data in your workspace could be included in agent context unintentionally.
- **Availability of external services.** The agent depends on the GitHub Copilot SDK, Azure services, and third-party APIs. Outages in any of these can cause failures or degraded behavior.

This is not a theoretical list. These are real failure modes of autonomous agents. You should be comfortable with these risks before deploying Polyclaw in any environment that matters.

---

## What We Have Built So Far

The project includes several controls today, but none of them have been formally audited. They represent a best-effort starting point.

### Authentication

| Layer | Mechanism |
|---|---|
| Admin API | Bearer token (`ADMIN_SECRET`) required on all `/api/*` routes. See [Security & Auth](/configuration/security/). |
| Bot channels | JWT validation via `botbuilder-core` SDK. |
| Voice callbacks | RS256 JWT validation; query-param callback token as secondary check. |
| Telegram | User ID whitelist (`TELEGRAM_WHITELIST`). Non-whitelisted messages are dropped. |
| Tunnel | `TUNNEL_RESTRICTED` limits the Cloudflare tunnel to bot and voice endpoints only. |
| Frontend | Login gate -- the SPA renders no data until `ADMIN_SECRET` is verified. |

### Secret Management

- Secrets can be stored in Azure Key Vault and referenced via `@kv:` prefix notation. See [Key Vault](/configuration/keyvault/).
- `ADMIN_SECRET` is auto-generated with `secrets.token_urlsafe(24)` if not explicitly set.
- A `SECRET_ENV_KEYS` frozenset enumerates which variables are treated as secrets.

### Isolation

- Code execution can be redirected to isolated sandbox sessions where the remote environment has no access to credentials or the host filesystem. See [Sandbox](/features/sandbox/).
- An experimental `LOCKDOWN_MODE` flag rejects all admin API requests, allowing you to freeze the agent immediately. See [Security & Auth](/configuration/security/).
- The Cloudflare tunnel is currently the only path that exposes the server to the internet. Without it, the admin API is localhost-only. The tunnel was added primarily for local development convenience. The plan is to remove the tunnel dependency for Azure deployments and replace it with cloud-native networking (Azure Container Apps ingress, private endpoints, managed identity).

### Transparency

- Every tool call is surfaced in the chat interface with the tool name, parameters, and result.
- The agent's behavioral guidelines live in a human-readable `SOUL.md` file. You can inspect and modify it.
- System prompts are assembled from version-controlled Markdown templates in `app/runtime/templates/`.
- All conversations are archived with full message and tool-call history.
- Structured logging with context tags (`[agent.start]`, `[chat.dispatch]`) covers all operations.

### Preflight and Disclaimers

- The [Setup Wizard](/getting-started/setup-wizard/) runs validation checks (JWT, tunnel, endpoints) before the agent starts.
- The web frontend requires users to accept a disclaimer about the agent's autonomous nature before proceeding.

---

## What Is Missing

The following areas are known gaps that the project intends to address:

- **Rate limiting.** There are no built-in rate limits on API calls, tool executions, or scheduled tasks.
- **Fine-grained permissions.** The agent currently has access to all configured credentials. There is no per-tool or per-skill scoping of secrets.
- **Multi-tenant isolation.** Polyclaw is designed for single-operator use. Running it for multiple users would require significant changes.

Security hardening is the next major development priority.

---

## Recommendations for Early Adopters

1. **Do not run Polyclaw against production accounts or infrastructure.** Use a dedicated test environment with scoped credentials.
2. **Set a strong `ADMIN_SECRET`** and store it in a key vault rather than in plaintext.
3. **Enable `TUNNEL_RESTRICTED`** to limit what is exposed through the tunnel.
4. **Set `TELEGRAM_WHITELIST`** if you use the Telegram channel.
5. **Enable sandbox execution** for code-running workloads to isolate them from the host.
6. **Monitor logs and session archives** to review what the agent has been doing.
7. **Review `SOUL.md`** and system prompt templates to make sure the agent's instructions match your expectations.
8. **Do not leave the agent running unattended** for extended periods without checking in on its activity.
