---
title: "REST API"
weight: 2
---

# REST API

All endpoints require `Authorization: Bearer <ADMIN_SECRET>` unless otherwise noted.

## Health

### `GET /health`

**Auth**: None

```json
{ "status": "ok", "version": "4.0.0" }
```

## Auth

### `POST /api/auth/check`

**Auth**: None (validates the provided token)

Returns 200 if the token is valid, 401 otherwise.

## Setup

### `GET /api/setup/status`

Returns setup completion state (identity configured, channels ready).

## Sessions

### `GET /api/sessions`

List all archived sessions.

### `GET /api/sessions/:id`

Get a specific session with message history.

### `DELETE /api/sessions/:id`

Delete a session.

## Skills

### `GET /api/skills`

List all available skills with source, description, and usage count.

### `POST /api/skills/install`

Install a skill from marketplace. Body: `{ name }` or `{ url }`.

### `POST /api/skills/contribute`

Contribute a user-created skill.

### `DELETE /api/skills/:id`

Delete a user-created skill.

### `GET /api/skills/marketplace`

List available skills from remote catalogs.

## Plugins

### `GET /api/plugins`

List all plugins.

### `POST /api/plugins/:id/enable`

Enable a plugin.

### `POST /api/plugins/:id/disable`

Disable a plugin.

### `POST /api/plugins/import`

Upload a plugin ZIP file. Multipart form data.

## MCP Servers

### `GET /api/mcp/servers`

List all MCP server configurations.

### `POST /api/mcp/servers`

Add a new MCP server. Body: `{ name, type, command?, args?, url?, enabled }`.

### `PUT /api/mcp/servers/:id`

Update an MCP server. Body: `{ enabled }`.

### `DELETE /api/mcp/servers/:id`

Delete an MCP server.

## Schedules

### `GET /api/schedules`

List all scheduled tasks.

### `POST /api/schedules`

Create a task. Body: `{ description, cron?, run_at?, prompt }`.

### `PUT /api/schedules/:id`

Update a task. Body: `{ enabled?, cron?, prompt? }`.

### `DELETE /api/schedules/:id`

Delete a task.

## Profile

### `GET /api/profile`

Get the agent profile (name, emoji, stats, heatmap).

### `POST /api/profile`

Update profile fields. Body: partial profile object.

## Proactive

### `GET /api/proactive`

Get proactive messaging state (enabled, pending, preferences).

### `PUT /api/proactive/enabled`

Set proactive messaging on or off. Body: `{ enabled }`.

### `PUT /api/proactive/preferences`

Update proactive preferences. Body: `{ min_gap_hours?, max_daily?, avoided_topics?, preferred_times? }`.

## Voice

### `POST /api/voice/call`

Initiate a voice call. Body: `{ number }`.

### `GET /api/voice/status`

Get current call status.

## Models

### `GET /api/models`

List available LLM models from the Copilot SDK.

## Sandbox

### `GET /api/sandbox/config`

Get sandbox configuration.

### `POST /api/sandbox/config`

Update sandbox config. Body: `{ enabled, session_pool_endpoint? }`.

## Environments

### `GET /api/environments`

List deployment environments.

### `GET /api/environments/audit`

Run an audit across deployment environments.

## Workspace

### `GET /api/workspace/list`

List workspace files.

### `GET /api/workspace/read`

Get file content.

## Network

### `GET /api/network/info`

Get network info (tunnel status, endpoints, connections).

## Bot Framework

### `POST /api/messages`

**Auth**: Bot Framework SDK validation (not Bearer token)

Bot Framework webhook endpoint. Receives activities from Azure Bot Service.

## ACS Callbacks

### `POST /acs`

**Auth**: JWT validation

Azure Communication Services callback endpoint.

### `POST /acs/incoming`

**Auth**: JWT validation

ACS incoming call handler.

### `GET /realtime-acs`

**Auth**: JWT validation

WebSocket endpoint for ACS media streaming.
