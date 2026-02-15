---
name: web-search
description: 'Search the web for information using Playwright browser automation. Use when the user asks to find, look up, or research something online.'
metadata:
  verb: search
---

# Web Search Skill

Use the Playwright MCP browser tools to search the web.

## Steps

1. Navigate to `https://www.google.com/search?q=<URL-encoded query>`
2. Wait for results to load
3. Extract the top 5 result titles, URLs, and snippets
4. If the user needs more detail, click into the most relevant result and extract key content
5. Summarize findings concisely with source links

## Tips

- For news queries, add `&tbm=nws` to the Google URL
- For recent results, add `&tbs=qdr:d` (past day) or `&tbs=qdr:w` (past week)
- Always cite sources with URLs
- If Google blocks you, try DuckDuckGo: `https://duckduckgo.com/?q=<query>`
