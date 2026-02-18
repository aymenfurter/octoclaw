---
title: "Built-in Skills"
weight: 3
---

# Built-in Skills

Octoclaw ships with these skills in the `skills/` directory.

## Daily Briefing

| Field | Value |
|---|---|
| **Verb** | `brief` |
| **Description** | Morning summary from memory daily logs and topic notes |

Generates a comprehensive daily briefing from the agent's consolidated memories. Covers recent conversations, pending tasks, and notable topics.

### Usage

```
Give me my daily briefing
brief
```

### How It Works

1. Reads daily log files from `~/.octoclaw/memory/daily/`
2. Reads topic notes from `~/.octoclaw/memory/topics/`
3. Synthesizes a morning summary with key points, pending items, and context

---

## Note Taking

| Field | Value |
|---|---|
| **Verb** | `note` |
| **Description** | File-based note management in `~/notes/` |

Creates, reads, updates, and organizes notes stored as files in the user's home directory.

### Usage

```
note: remember to update the API docs
note list
note search deployment
```

### How It Works

1. Notes are stored as text files in `~/notes/`
2. Supports create, read, list, search, and delete operations
3. File names are derived from the note content or user-specified titles

---

## Summarize URL

| Field | Value |
|---|---|
| **Verb** | `summarize` |
| **Description** | Playwright-based web page content extraction |

Navigates to a URL using the Playwright MCP server and extracts the main content for summarization.

### Usage

```
summarize https://example.com/article
```

### How It Works

1. Uses Playwright MCP to navigate to the URL
2. Extracts the main content (article body, headings, key paragraphs)
3. Generates a structured summary with key points

### Requirements

- Playwright MCP server must be enabled
- Chromium must be installed (`npx playwright install chromium`)

---

## Web Search

| Field | Value |
|---|---|
| **Verb** | `search` |
| **Description** | Google/DuckDuckGo search via Playwright browser automation |

Performs web searches and summarizes results using browser automation.

### Usage

```
search latest developments in quantum computing
```

### How It Works

1. Uses Playwright MCP to open a search engine
2. Enters the search query
3. Extracts and summarizes the top results
4. Optionally follows links for deeper content

### Requirements

- Playwright MCP server must be enabled
- Chromium must be installed
