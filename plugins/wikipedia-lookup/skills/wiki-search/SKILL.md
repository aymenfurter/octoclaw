---
name: wiki-search
description: |
  Search Wikipedia for articles matching a query. Returns a list of matching page titles.
  Use when the user says: "search wikipedia for", "find wikipedia articles about",
  "what does wikipedia have on", "look up on wikipedia"
metadata:
  verb: search
---

# Wikipedia Search Skill

Search Wikipedia and return matching article titles so the user can pick one to read.

## Steps

### 1. Search Wikipedia

Run a Python snippet to search:

```bash
python3 -c "
import wikipedia
import json

results = wikipedia.search('QUERY', results=10)
print(json.dumps(results, indent=2))
"
```

Replace `QUERY` with the user's search term.

### 2. Handle Disambiguation

If the search returns ambiguous results, the `wikipedia` package may raise a `DisambiguationError`. Catch it and present the options:

```bash
python3 -c "
import wikipedia
import json

try:
    results = wikipedia.search('QUERY', results=10)
    print(json.dumps(results, indent=2))
except wikipedia.exceptions.DisambiguationError as e:
    print(json.dumps({'disambiguation': True, 'options': e.options[:15]}, indent=2))
"
```

### 3. Present Results

```markdown
## Wikipedia Search: "<query>"

Found X matching articles:
1. <Article Title 1>
2. <Article Title 2>
3. <Article Title 3>
...

Ask me to summarize any of these, or say "tell me about <title>" for details.
```

### 4. Summary

Tell the user how many results were found and list the top matches. If there was a disambiguation, explain that the term has multiple meanings and list the options.
