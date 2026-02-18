---
title: "Marketplace"
weight: 2
---

# Skill Marketplace

Octoclaw supports discovering and installing skills from remote catalogs hosted on GitHub.

## Remote Catalogs

The skill registry fetches catalogs from configured GitHub repositories:

- `github/awesome-copilot`
- `anthropics/skills`

Each catalog is a repository containing skill directories with `SKILL.md` files.

## How It Works

1. The registry fetches the catalog index from GitHub
2. Available skills are listed with name, description, and commit count
3. Users can install skills directly from the marketplace
4. Downloaded skills are placed in `~/.octoclaw/skills/` with a `.origin` file

## Caching

- Catalog responses are cached with a **300-second TTL**
- GitHub API rate limits are handled gracefully with retry logic
- Commit counts are tracked to indicate skill maturity

## Installing from Marketplace

### Via Web Dashboard

Navigate to **Skills** and open the **Marketplace** tab. Browse available skills and click **Install**.

![Skill marketplace](/screenshots/web-customization-skillmarketplace.png)

### Via API

```bash
# List marketplace skills
GET /api/skills/marketplace

# Install a skill
POST /api/skills/install
{ "name": "code-review" }
```

## Updating Skills

Marketplace skills can be updated by reinstalling them. The existing skill directory is replaced with the latest version from the catalog.

## Publishing Skills

To make your skills available in the marketplace:

1. Create a GitHub repository with your skill directories
2. Each skill must have a valid `SKILL.md` with frontmatter
3. Submit a PR to the catalog repository to include your skills
