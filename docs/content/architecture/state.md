---
title: "State Management"
weight: 3
---

# State Management

Octoclaw uses a file-based state system with JSON stores. All state files live under `OCTOCLAW_DATA_DIR` (default: `~/.octoclaw/`).

## State Modules

### Session Store

**File**: `sessions/<session_id>.json`

Each chat session is persisted as a separate JSON file containing message history, metadata, and timestamps.

| Feature | Description |
|---|---|
| One file per session | Easy inspection and backup |
| Archival policies | `24h`, `7d`, `30d`, `never` |
| Session resume | Last 20 messages loaded as context |
| Metadata | Model used, message count, timestamps |

### Memory Store

**Directory**: `memory/`

The memory system consolidates chat interactions into long-term memories:

- **`daily/`** -- Daily log files summarizing interactions
- **`topics/`** -- Topic-specific notes extracted from conversations

Memory formation is triggered after `MEMORY_IDLE_MINUTES` (default: 5) of inactivity. The `MEMORY_MODEL` LLM generates structured summaries from buffered chat turns.

### Profile Store

**File**: `profile.json`

Tracks the agent's identity and behavioral state:

| Field | Description |
|---|---|
| `name` | Agent display name |
| `emoji` | Visual identity |
| `location` | Timezone context |
| `emotional_state` | Current mood (affects responses) |
| `preferences` | Communication style preferences |
| `skill_usage` | Usage counts per skill |
| `interaction_log` | Recent interaction timestamps |
| `contribution_heatmap` | Activity by hour/day |

### MCP Config

**File**: `mcp_servers.json`

Stores MCP server definitions. Supports four server types:

| Type | Description |
|---|---|
| `local` | Spawned as a subprocess |
| `stdio` | Communicates via stdin/stdout |
| `http` | Remote HTTP endpoint |
| `sse` | Server-Sent Events endpoint |

### Proactive State

**File**: `proactive.json`

Manages autonomous proactive messaging:

| Field | Description |
|---|---|
| `enabled` | Whether proactive messaging is active |
| `pending` | Single pending message awaiting delivery |
| `sent` | Last 100 sent messages |
| `preferences` | Timing, frequency, and topic constraints |
| `daily_count` | Messages sent today |

### Other State Files

| File | Purpose |
|---|---|
| `SOUL.md` | Agent personality definition |
| `scheduler.json` | Scheduled task definitions |
| `deploy_state.json` | Deployment records |
| `infra_config.json` | Infrastructure configuration |
| `plugin_config.json` | Plugin enabled/disabled state |
| `sandbox_config.json` | Sandbox configuration |
| `foundry_iq_config.json` | Azure AI Foundry IQ settings |
| `conversation_references.json` | Bot Framework conversation references |

## Design Principles

- **No database required** -- everything is flat files for simplicity and portability
- **Human-readable** -- JSON and Markdown files can be inspected and edited manually
- **Docker-friendly** -- mount `~/.octoclaw` as a volume for persistence
- **Atomic writes** -- state modules use write-then-rename for crash safety
