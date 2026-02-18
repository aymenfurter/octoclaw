---
title: "Sandbox Execution (Experimental)"
weight: 5
---

# Sandbox Execution (Experimental)

Octoclaw can execute code in isolated sandbox environments using [Azure Container Apps Dynamic Sessions](https://learn.microsoft.com/en-us/azure/container-apps/sessions). Sandbox mode is **disabled by default**.

## How It Works

Octoclaw runs inside its own container and normally has full access to Azure credentials, the local filesystem, and all configured services. When sandbox mode is enabled, the agent's code-execution tool calls are intercepted and redirected to a **remote** container session instead of running on the host.

The flow looks like this:

1. The agent decides to execute code (shell command, script, etc.)
2. Relevant files and data are packaged into a ZIP archive and **uploaded** to the remote dynamic session
3. The code runs inside that remote container via `bootstrap.sh`
4. Results and generated files are **synced back** to the local environment

This means the agent's code never touches the host container directly. The remote session is a throwaway environment with no access to Octoclaw's own container, its Azure credentials, or any of its infrastructure.

### Why This Matters

Because the dynamic session is a separate, sandboxed container:

- **Azure auth context is not propagated.** The remote session cannot call Azure APIs, access Key Vault secrets, or interact with any Azure resource. This is the primary security benefit -- even if the agent generates malicious code, it cannot compromise your Azure environment.
- **The agent cannot modify itself.** Code runs in an ephemeral container that is destroyed after use, so there is no way for the agent to alter its own configuration, files, or runtime.

The trade-off is that sandboxed execution is **less powerful**. Any workflow that requires the agent to automate Azure resources (e.g. provisioning infrastructure, querying Azure APIs, managing Key Vault) will not work from within the sandbox. Those operations must happen outside of sandboxed tool calls.

<div class="callout callout--info">
<strong>GitHub login is still required.</strong> The agent itself runs on the GitHub Copilot SDK, which requires GitHub authentication. Enabling sandbox mode does not change this requirement -- the sandbox isolates <em>code execution</em>, not the agent's model or tool invocation layer.
</div>

### Data Synchronization

- **Upload**: Whitelisted directories are zipped and uploaded to the session before execution
- **Download**: Results and new files are merged back to the local environment after execution
- **Session reuse**: Active sessions are reused until the idle timeout (60 seconds)

## Configuration

### Enable Sandbox

Via the web dashboard **Sandbox** page or via API:

```bash
POST /api/sandbox/config
{
  "enabled": true,
  "session_pool_endpoint": "https://your-pool.eastus.azurecontainerapps.io"
}
```

![Sandbox configuration](/screenshots/web-infra-sandboxconfig.png)

### Requirements

| Requirement | Description |
|---|---|
| Azure Container Apps | Dynamic sessions pool provisioned |
| Azure credentials | `AzureCliCredential` or `DefaultAzureCredential` |
| Pool endpoint | URL to the dynamic sessions pool |

## Benefits

- **Security**: Code runs in an isolated container, not on the host. Azure auth context is not propagated, protecting your cloud environment.
- **Reproducibility**: Clean environment for each session (sessions are reused within the idle window, then destroyed)
- **Resource isolation**: Container resources are completely separate from the server

## Session Lifecycle

1. **Create**: A new session is created when the first tool call is intercepted
2. **Reuse**: Subsequent tool calls use the same session
3. **Idle reaper**: Sessions are cleaned up after 60 seconds of inactivity
4. **Data sync**: Files are synchronized on each tool call boundary

## Token Acquisition

Authentication to the Dynamic Sessions API uses:

1. `AzureCliCredential` (local development)
2. `DefaultAzureCredential` (production / managed identity)

## Limitations

<div class="callout callout--warning">
<strong>Experimental feature.</strong> Sandbox execution has not yet been widely tested in replicated (multi-instance) deployments. It may also conflict with parallel agent sessions, since multiple concurrent tool calls could race against the same dynamic session. Avoid enabling sandbox mode if you are running parallel sessions or multi-replica deployments until further testing has been completed.
</div>

- Sandboxed code **cannot** access Azure APIs, Key Vault, or any Azure resource (auth context is intentionally not forwarded)
- Workflows that require Azure automation must run outside the sandbox
- **File tools are disabled.** When sandbox mode is active, the agent's built-in file-management tools are removed and the agent is instructed to use terminal commands instead (e.g. `cat`, `sed`, `mv`). This ensures all file operations go through the sandboxed session rather than the host filesystem.
- **Some MCP servers and plugins may break.** Many MCP servers are built to interact with the local filesystem directly. Since sandbox execution redirects all terminal activity to a remote container that has no access to the host's files or services, MCP tools that depend on the local environment will fail. This is an inherent trade-off of sandboxing.
- **Latency impact**: Session creation adds significant latency on the first tool call (provisioning, uploading code and data archives, running bootstrap). Subsequent tool calls within the same session are much faster since the session is already warm.
- Parallel agent sessions may conflict with sandbox session management
- Not yet validated in multi-replica Container Apps deployments
