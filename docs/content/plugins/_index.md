---
title: "Plugins & MCP"
weight: 50
---

Polyclaw extends its capabilities through two complementary systems: **Plugins** and **MCP Servers**.

## What is MCP?

The **Model Context Protocol** (MCP) is an open standard for connecting AI models to external tools and data sources. MCP servers expose callable functions that the LLM can invoke during conversations.

Polyclaw supports four MCP server types:

| Type | Description |
|---|---|
| `local` | Spawned as a subprocess, communicates via stdio |
| `stdio` | External process with stdin/stdout transport |
| `http` | Remote HTTP endpoint |
| `sse` | Server-Sent Events endpoint |

## What are Plugins?

Plugins are bundles that package skills, metadata, and dependency declarations together. They provide a higher-level abstraction for distributing and managing sets of related capabilities.

Each plugin contains:

- A `PLUGIN.json` manifest
- One or more skill directories
- Optional dependency declarations (CLI tools, pip packages)
- Optional setup flow (a skill that guides first-time configuration)

## How They Work Together

```
Plugin
  |-- PLUGIN.json (metadata, dependencies)
  |-- skills/
  |     |-- skill-a/SKILL.md
  |     |-- skill-b/SKILL.md
```

Plugins and MCP servers are **managed independently** but work well together. For example, a plugin can ship a skill that instructs the agent to use Playwright for browser automation, or a skill that relies on the WorkIQ MCP server for Microsoft 365 data.

When a plugin is enabled:
1. Its skill directories are copied to the user skills directory
2. Dependencies are checked

When disabled:
1. Skill directories are removed

## Sections

- [MCP Servers](/plugins/mcp-servers/) -- Configuration and built-in MCP servers
- [Creating Plugins](/plugins/creating-plugins/) -- Plugin manifest format and development guide
- [Bundled Plugins](/plugins/bundled/) -- Documentation for included plugins
