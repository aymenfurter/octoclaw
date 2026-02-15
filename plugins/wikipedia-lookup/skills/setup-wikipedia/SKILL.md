---
name: setup-wikipedia
description: |
  Install the wikipedia Python package for querying Wikipedia articles.
  This is a one-time setup skill.
  Use when the user says: "setup wikipedia", "install wikipedia package"
metadata:
  verb: setup
---

# Wikipedia Package Setup

Install the `wikipedia` Python package to enable Wikipedia lookups.

## Step 1 -- Install the Package

```bash
pip install wikipedia
```

## Step 2 -- Verify Installation

```bash
python3 -c "import wikipedia; print('wikipedia package version:', wikipedia.__version__)"
```

If this prints a version string, the package is ready.

## Step 3 -- Quick Test

```bash
python3 -c "import wikipedia; print(wikipedia.summary('Python (programming language)', sentences=1))"
```

If this returns a sentence about Python, everything is working.
