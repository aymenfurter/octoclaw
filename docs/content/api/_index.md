---
title: "API Reference"
weight: 70
---

Octoclaw exposes a REST API and a WebSocket endpoint for the admin dashboard and external integrations.

## Authentication

All `/api/*` endpoints require a Bearer token:

```
Authorization: Bearer <ADMIN_SECRET>
```

Exceptions are listed in the [Security](/configuration/security/) section.

## Base URL

- **Local**: `http://localhost:8000`
- **Docker**: `http://localhost:8080`

## Sections

- [WebSocket Chat](/api/websocket/) -- Real-time chat protocol
- [REST API](/api/rest/) -- CRUD endpoints for all resources
