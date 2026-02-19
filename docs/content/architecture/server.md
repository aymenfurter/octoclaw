---
title: "Server & Middleware"
weight: 2
---

# Server & Middleware

The Polyclaw server is an aiohttp web application that hosts the admin dashboard, chat WebSocket, Bot Framework endpoint, and voice routes.

## Application Setup

Defined in `app/runtime/server/app.py`. The server creates an `aiohttp.web.Application` with middleware, routes, background tasks, and lifecycle hooks.

### Entry Points

| Command | Port | Description |
|---|---|---|
| `polyclaw-admin` | 8000 (configurable) | Admin server + bot endpoint |
| `polyclaw-bot` | 3978 (configurable) | Bot endpoint only |

## Middleware Stack

Middleware is applied in order to every request:

### 1. Lockdown Middleware

When `LOCKDOWN_MODE=true`, all API requests are rejected with `403`. The intent is to allow operators to disable the agent from the web UI and later re-enable it via a bot service channel (e.g. `/lockdown off` in Teams or Telegram). Bot and voice endpoints remain open during lockdown. This feature is experimental and not yet fully implemented.

### 2. Tunnel Restriction Middleware

When `TUNNEL_RESTRICTED=true`, requests arriving through the Cloudflare tunnel are restricted to bot and voice endpoints only. This prevents public access to the admin API while keeping bot callbacks functional.

### 3. Auth Middleware

Bearer token validation on all `/api/*` routes. Compares the `Authorization: Bearer <token>` header against `ADMIN_SECRET`. Also accepts `?token=` or `?secret=` query parameters as alternatives.

Non-API paths -- the SPA frontend (`/`, `/assets/*`, `favicon.ico`, etc.), `/media/*` files, and `/health` -- are served **without** authentication. The frontend enforces its own login gate in JavaScript: the user must enter `ADMIN_SECRET` before the React app renders any dashboard content. This means the HTML, CSS, and JS bundles are publicly accessible, but they contain no secrets or data. All sensitive operations go through `/api/*` endpoints that require the Bearer token.

**Public API paths** (exempt from Bearer auth):

| Path | Own security |
|---|---|
| `/health` | None (read-only health check) |
| `/api/messages` | Validated by the Bot Framework SDK (app ID + password) |
| `/api/voice/acs-callback`, `/acs` | Query-param callback token + RS256 JWT against Microsoft JWKS |
| `/api/voice/media-streaming`, `/realtime-acs` | Query-param callback token + RS256 JWT against Microsoft JWKS |
| `/api/auth/check` | Intentionally open. Returns `{"authenticated": true/false}` without exposing secrets. |

All other `/api/voice/*` routes (e.g. `/api/voice/call`, `/api/voice/status`) **do** require Bearer auth like any normal API endpoint.

## Route Groups

The server registers routes from modular handler classes:

| Handler | Prefix | Purpose |
|---|---|---|
| `ChatHandler` | `/api/chat/` | WebSocket chat, suggestions |
| `SessionRoutes` | `/api/sessions/` | Session CRUD |
| `SkillRoutes` | `/api/skills/` | Skill management |
| `McpRoutes` | `/api/mcp/` | MCP server configuration |
| `PluginRoutes` | `/api/plugins/` | Plugin management |
| `SchedulerRoutes` | `/api/schedules/` | Task scheduling |
| `ProfileRoutes` | `/api/profile/` | Agent profile |
| `ProactiveRoutes` | `/api/proactive/` | Proactive messaging |
| `EnvironmentRoutes` | `/api/environments/` | Deployment environments |
| `SandboxRoutes` | `/api/sandbox/` | Sandbox configuration |
| `FoundryIQRoutes` | `/api/foundry-iq/` | Azure AI Foundry IQ |
| `SetupRoutes` | `/api/setup/` | Setup wizard state |
| `VoiceSetupRoutes` | `/api/voice/setup/` | Voice configuration |
| `BotEndpoint` | `/api/messages` | Bot Framework webhook |
| `VoiceRoutes` | `/api/voice/` | Voice call management |
| `WorkspaceHandler` | `/api/workspace/` | Workspace files |
| `NetworkRoutes` | `/api/network/` | Network topology |

### Static Assets

- `/media/*` -- Serves files from the media directory
- `/*` -- SPA catch-all serving the frontend `index.html`

## Lifecycle Hooks

### on_startup

1. Start background tasks: scheduler loop, proactive delivery loop, Foundry IQ index loop, deployment reconciliation
2. Provision infrastructure: start Cloudflare tunnel, deploy Azure Bot (if configured)

### on_cleanup

1. Decommission infrastructure: stop tunnel, clean up bot resources
2. Stop the agent and close all sessions

## Health Check

`GET /health` returns:

```json
{
  "status": "ok",
  "version": "4.0.0"
}
```
