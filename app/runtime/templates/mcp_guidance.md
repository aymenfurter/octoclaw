**Playwright** (local) -- Browser automation, web scraping, screenshots, form filling, and any task that requires interacting with a web page. Use this when the user asks you to visit a URL, take a screenshot, extract content from a website, fill out a form, or automate any browser-based workflow. This is your primary web interaction tool.

---

**Microsoft Learn** (remote) -- Search and fetch official Microsoft documentation. Use this when the user asks about Azure services, Microsoft 365, .NET, PowerShell, Windows, Visual Studio, or any Microsoft technology. Prefer this over generic web search for Microsoft-related questions because the results are authoritative, up-to-date, and structured. Supports keyword search and full-page fetch.

---

**Azure MCP Server** (local) -- Direct management of Azure cloud resources. Use this when the user asks you to list, create, update, or delete Azure resources (resource groups, storage accounts, VMs, App Services, Cosmos DB, Key Vault, etc.), query Azure Resource Graph, manage deployments, or inspect Azure subscriptions. Authenticated via the local `az login` session. Prefer this over shell `az` commands when available -- it gives the AI structured, tool-call access to Azure.

---

**GitHub MCP Server** (local) -- Full GitHub API integration. Use this when the user asks about repositories, issues, pull requests, commits, branches, releases, GitHub Actions workflows, code search, or any GitHub operation. Prefer this over `gh` CLI or raw API calls -- it exposes structured tools for listing repos, creating issues, reviewing PRs, searching code, managing labels, and more.
