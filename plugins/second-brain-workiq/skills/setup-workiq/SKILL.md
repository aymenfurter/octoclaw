---
name: setup-workiq
description: |
  Install the WorkIQ CLI for Microsoft 365 integration.
  This is a one-time setup skill that downloads and configures the workiq binary.
  Use when the user says: "setup workiq", "install workiq", "configure workiq"
metadata:
  verb: setup
---

# WorkIQ CLI Setup

Install the WorkIQ CLI for accessing Microsoft 365 data (emails, meetings, documents, Teams messages).

WorkIQ runs as a native MCP server (`workiq mcp`) and is registered as a
built-in MCP server in polyclaw. This setup skill just ensures the binary
is installed and the user has authenticated.

## Step 1 -- Install via npm

```bash
npm install -g @microsoft/workiq
```

If the install fails with a globalization / ICU error on Linux, run:
```bash
apt-get update && apt-get install -y libicu-dev
```

## Step 2 -- Verify Installation

```bash
workiq version
```

If this prints a version string, the CLI is installed.

## Step 3 -- Accept EULA

```bash
workiq accept-eula || echo "accept-eula not needed in this version"
```

## Step 4 -- Authenticate

For the authentication, aks the user to ssh into the terminal and run "workiq ask -q 'Hello'" to trigger the Microsoft 365 sign-in flow.". WorkIQ currently does not support device code flow so this manual step is required for now.