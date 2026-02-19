---
title: "MCP Servers"
weight: 1
---

# MCP Servers

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) is an open standard that lets AI agents call external tools and access data sources. An MCP server is a lightweight process or service that exposes a set of tools -- the agent discovers them automatically and can invoke them during conversations.

This is how Polyclaw gets capabilities like browser automation, Azure resource management, documentation search, and GitHub integration without any of that logic living inside the agent itself. You enable the MCP servers you need, and the agent gains their tools.

## Managing MCP Servers

The web dashboard is the easiest way to discover, add, and manage MCP servers.

### Discover and Browse

The **MCP Servers** page lists all configured servers along with their type, status, and a toggle to enable or disable each one.

![MCP server list](/screenshots/web-customization-enablecustommcpmslearn.png)

### Marketplace

The discovery page lets you browse a catalog of available MCP servers and enable them with one click.

![MCP server marketplace](/screenshots/web-customization-mcpserverdiscoverpage.png)

### Adding a Server

You can add any MCP server -- local or remote -- through the dashboard. Specify whether it is a local subprocess or a remote HTTP/SSE endpoint, provide the connection details, and save.

![Adding a remote or local MCP server](/screenshots/web-customization-add-remote-or-localmcpserver.png)

### Slash Commands

```
/mcp                    # List all MCP servers
/mcp enable <id>        # Enable a server
/mcp disable <id>       # Disable a server
/mcp add <name> <url>   # Add a new server definition
/mcp remove <id>        # Remove a server
```

### API

```bash
GET  /api/mcp/servers                # List servers
POST /api/mcp/servers                # Add server
PUT  /api/mcp/servers/<id>           # Toggle / update server
DELETE /api/mcp/servers/<id>         # Remove server
```

## Using MCP Tools in Conversations

Once an MCP server is enabled, the agent can use its tools immediately -- no extra prompting required. The agent discovers available tools at session start and decides when to call them based on your request.

### Example: Microsoft Learn

Enable the Microsoft Learn MCP server, then ask the agent to look something up in the docs.

![Using Microsoft Learn MCP in chat](/screenshots/web-chat-useenabledmcpmslearninchat.png)

### Example: Playwright Browser

The Playwright MCP server gives the agent a full headless browser. It can navigate pages, fill forms, take screenshots, and extract content.

![Using Playwright browser automation in chat](/screenshots/web-chat-useplaywrightbrowser.png)

## How It Works Under the Hood

1. On session creation, all enabled MCP servers are passed to the Copilot SDK
2. The SDK connects to each server and discovers its tools via `tools/list`
3. MCP server descriptions are included in the agent's system prompt
4. During conversation, the LLM can call any tool exposed by connected servers
5. Tool results are returned to the LLM as context for generating responses

## Server Types

Polyclaw supports four transport types:

| Type | Description |
|---|---|
| `local` | Subprocess spawned by Polyclaw, communicates via stdio |
| `stdio` | External process with stdin/stdout transport |
| `http` | Remote HTTP endpoint |
| `sse` | Server-Sent Events endpoint |

## Built-in MCP Servers

Polyclaw ships with several pre-configured MCP servers:

| Server | Type | Default | Purpose |
|---|---|---|---|
| **Playwright** | local | Enabled | Browser automation (web search, scraping, UI testing) |
| **Microsoft Learn** | http | Disabled | Search Microsoft documentation |
| **Azure MCP Server** | local | Disabled | Azure resource management (requires `az login`) |
| **GitHub MCP Server** | local | Disabled | GitHub API integration (requires `gh auth login`) |

## Configuration Storage

MCP server definitions are stored in `~/.polyclaw/mcp_servers.json`. Each entry specifies a server type, connection details, and metadata. You rarely need to edit this file directly -- the dashboard and slash commands manage it for you.

## Adding Custom MCP Servers

Any process that implements the MCP protocol can be added. The server must:

1. Accept connections via the configured transport (stdio, HTTP, or SSE)
2. Respond to `tools/list` to enumerate available tools
3. Handle `tools/call` to execute tool invocations
4. Return structured results

See the [MCP specification](https://modelcontextprotocol.io/) for the full protocol definition.
