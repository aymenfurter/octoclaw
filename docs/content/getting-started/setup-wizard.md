---
title: "Setup Wizard"
weight: 3
---

# Setup Wizard

Once octoclaw finishes building and passes its health check, the TUI automatically opens the Setup screen in your default browser. From here you configure authentication, bot settings, and infrastructure.

## Setup Screen

![Setup screen](/screenshots/web-setupdone.png)

### Authentication

<div class="callout callout--warning" style="margin-top:12px">
<p class="callout__title">Understand what these logins mean</p>
<p><strong>Both Azure Login and GitHub Login are required during setup.</strong> You cannot skip either one at this stage.</p>

<p><strong>GitHub Login</strong> authenticates with GitHub Copilot. The Copilot SDK is the agent&rsquo;s reasoning engine&mdash;without it, octoclaw cannot function. This authentication must remain active for the lifetime of the agent. Your GitHub account determines which Copilot models and rate limits are available.</p>

<p><strong>Azure Login</strong> signs you in with the Azure CLI. The agent then runs under <strong>your</strong> Azure identity. This is not a sandboxed chat interface like ChatGPT or Copilot Chat. octoclaw is an autonomous agent with tool-calling capabilities&mdash;it can create, modify, and delete real Azure resources, spend money on your subscription, and access any service your account has permissions for.</p>

<p>Before logging in, make sure you understand the implications:</p>
<ul>
<li><strong>The agent acts as you.</strong> Every Azure API call it makes carries your credentials. If your account can delete a resource group, so can the agent.</li>
<li><strong>Costs are yours.</strong> Resources the agent provisions (VMs, storage, databases) are billed to your subscription.</li>
<li><strong>There is no undo button.</strong> Deleted resources, overwritten secrets, and modified configurations may not be recoverable.</li>
</ul>
<p>To limit exposure, you can create a dedicated Azure subscription with restricted permissions and log in with that account instead. Alternatively, advanced users can SSH into the container terminal and authenticate as a service principal with scoped RBAC rather than using a personal account.</p>
<p>You can also enable <a href="/features/sandbox/">Sandbox Execution</a> to redirect tool calls that run code to an isolated Azure Container Apps session instead of the host machine. This adds another layer of containment for the agent&rsquo;s actions.</p>
</div>

Status indicators for Azure, GitHub, and tunnel connectivity. Each can be initiated directly from this page:

- **Azure Login** -- opens device-code flow for Azure CLI authentication
- **Azure Logout** -- signs out of the current Azure CLI session
- **GitHub Login** -- authenticates with GitHub Copilot via device code
- **Set GitHub Token** -- manually configure a GitHub PAT
- **Start Tunnel** -- starts a Cloudflare tunnel to expose the bot endpoint publicly

<div class="callout callout--info" style="margin-top:16px">
<p class="callout__title">You can sign out of Azure after setup</p>
<p>While signed in, the agent shares your Azure CLI session&mdash;it has the same access to your subscription as you do. Azure credentials are needed for provisioning and for runtime features like updating the Bot Service tunnel URL. If you sign out after setup, core agent functionality (chat, skills, scheduling) continues to work, but operations that require Azure API calls will fail until you sign back in.</p>
</div>

### Bot Configuration

A form for configuring the Bot Framework deployment:

- **Resource Group** -- Azure resource group for bot resources (default: `octoclaw-rg`)
- **Location** -- Azure region (default: `eastus`)
- **Bot Display Name** -- display name for the Azure Bot resource
- **Telegram Token** -- Bot token from @BotFather (optional)
- **Telegram Whitelist** -- comma-separated list of allowed Telegram usernames

<div class="callout callout--danger" style="margin-top:12px">
<p class="callout__title">Set a Telegram whitelist</p>
<p>Without a whitelist, <strong>anyone</strong> who discovers your bot&rsquo;s Telegram handle can send it messages&mdash;and the agent will respond using <strong>your</strong> Azure identity and credentials. That means a stranger could instruct your agent to create resources, access data, or take actions on your subscription. Always set a whitelist with only the Telegram usernames you trust.</p>
</div>

### Infrastructure Actions

- **Save Configuration** -- persists bot and channel settings
- **Deploy Infrastructure** -- provisions Azure Bot Service, channels, and related resources
- **Decommission Infrastructure** -- tears down deployed Azure resources
- **Run Preflight Checks** -- validates bot credentials, JWT, tunnel, endpoint auth, and channel security
- **Run Smoke Test** -- end-to-end connectivity test for Copilot

![Preflight checks](/screenshots/web-infra-preflight.png)

## Identity Setup (Web Dashboard)

On first launch, the agent detects whether identity has been configured by checking the `SOUL.md` file and profile state. If not configured, a **bootstrap prompt** activates that walks through the setup conversationally.

### Steps

1. **Identity** -- the agent chooses a name, emoji, location, and personality traits for itself
2. **SOUL.md** -- a Markdown file at `~/.octoclaw/SOUL.md` defining the agent's personality, communication style, and behavioral guidelines. Used as part of the system prompt for every interaction.
3. **Channel setup** (optional) -- if Bot Framework credentials are configured, the wizard can start a tunnel, deploy a bot resource, and configure Teams or Telegram channels
4. **Completion** -- the bootstrap prompt deactivates and the agent switches to normal operation

![Agent profile configuration](/screenshots/web-agentprofile.png)

### Re-running Setup

To reset identity and re-enter the wizard:

1. Delete `~/.octoclaw/SOUL.md`
2. Clear the profile state via `/profile` commands or delete `~/.octoclaw/agent_profile.json`
3. Restart Octoclaw

## Customization Page

The web dashboard includes a **Customization** page that gives an overview of everything you can configure on your agent:

- Skills -- installed and self-created agent skills
- Plugins -- active MCP plugin connections
- MCP Servers -- registered Model Context Protocol servers
- Scheduling -- recurring and one-shot scheduled tasks

![Customization main page](/screenshots/web-customization-main-page.png)
