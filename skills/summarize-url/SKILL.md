---
name: summarize-url
description: 'Summarize the content of a given URL. Use when the user provides a link and asks for a summary or key points.'
metadata:
  verb: summarize
---

# Summarize URL Skill

Use Playwright to extract and summarize web page content.

## Steps

1. Navigate to the target URL using Playwright browser tools
2. Wait for the page to fully load
3. Extract the main content (article body, ignoring navigation/ads/footers)
4. Produce a concise summary with:
   - **Title** of the page
   - **Key points** (3-5 bullet points)
   - **Full summary** (2-3 paragraphs if the user wants detail)
5. Note the source URL at the bottom

## Tips

- For paywalled sites, try extracting what's visible
- For PDFs, note that Playwright may not render them well -- suggest the user share the text directly
- Strip boilerplate (cookie banners, navbars) from the summary
