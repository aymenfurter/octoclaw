---
title: "WebSocket Chat"
weight: 1
---

# WebSocket Chat Protocol

The primary chat interface uses a WebSocket connection at `/api/chat/ws`.

## Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/api/chat/ws');
```

The WebSocket includes auto-reconnect logic with a 3-second delay.

## Message Format

All messages are JSON objects with an `action` field.

### Client to Server

#### New Session

```json
{
  "action": "new_session"
}
```

#### Resume Session

```json
{
  "action": "resume_session",
  "session_id": "abc-123"
}
```

Loads the last 20 messages as context.

#### Send Message

```json
{
  "action": "send",
  "text": "Hello, how are you?",
  "model": "claude-sonnet-4-20250514"
}
```

### Server to Client

#### Text Delta

Streamed token-by-token during response generation:

```json
{
  "type": "delta",
  "content": "Here"
}
```

#### Tool Events

Sent as event messages when the agent invokes a tool:

```json
{
  "type": "event",
  "event": "tool_call",
  "data": {
    "name": "schedule_task",
    "arguments": { "description": "Daily report", "cron": "0 9 * * *" }
  }
}
```

#### Event

System events and status updates:

```json
{
  "type": "event",
  "event": "session_created",
  "data": { "session_id": "abc-123" }
}
```

#### Command Response

Response to slash commands (sent as a regular message):

```json
{
  "type": "message",
  "content": "Available models: ..."
}
```

#### Error

```json
{
  "type": "error",
  "content": "Session not found"
}
```

#### Done

Marks the end of a response:

```json
{
  "type": "done"
}
```

## Slash Commands via WebSocket

Slash commands are detected by the `CommandDispatcher` and handled server-side. Send them as regular messages:

```json
{
  "action": "send",
  "text": "/status"
}
```

## Suggestions

```
GET /api/chat/suggestions
```

Returns an array of suggested conversation starters.

## Models

```
GET /api/models
```

Returns available LLM models.

## Session Lifecycle

1. Client connects to WebSocket
2. Client sends `new_session` or `resume_session`
3. Server responds with `event: session_created`
4. Client sends messages, server streams deltas
5. On disconnect, the session is preserved for resume
