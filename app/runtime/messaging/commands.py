"""Shared slash-command dispatcher.

Centralises all slash-command logic so both the Bot Framework handler
and the WebSocket chat handler share a single implementation.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from ..agent.agent import Agent
from ..config.settings import cfg
from ..registries.plugins import get_plugin_registry
from ..registries.skills import get_registry as get_skill_registry
from ..scheduler import get_scheduler
from ..state.infra_config import InfraConfigStore
from ..state.mcp_config import McpConfigStore
from ..state.profile import load_profile
from ..state.session_store import SessionStore

BOOT_TIME = time.monotonic()

ReplyFn = Callable[[str], Awaitable[None]]


class ChannelContext(Protocol):
    @property
    def conversation_refs_count(self) -> int: ...

    @property
    def connected_channels(self) -> set[str]: ...

    @property
    def conversation_refs(self) -> list[Any]: ...


@dataclass
class CommandContext:
    text: str
    reply: ReplyFn
    channel: str
    channel_ctx: ChannelContext | None = None


class CommandDispatcher:
    _EXACT_COMMANDS: dict[str, str] = {
        "/new": "_cmd_new",
        "/status": "_cmd_status",
        "/skills": "_cmd_skills",
        "/session": "_cmd_session",
        "/channels": "_cmd_channels",
        "/clear": "_cmd_clear",
        "/help": "_cmd_help",
        "/plugins": "_cmd_plugins",
        "/mcp": "_cmd_mcp",
        "/schedules": "_cmd_schedules",
        "/sessions": "_cmd_sessions",
        "/profile": "_cmd_profile",
        "/config": "_cmd_config",
        "/preflight": "_cmd_preflight",
        "/call": "_cmd_call",
        "/models": "_cmd_models",
        "/change": "_cmd_change",
    }

    _PREFIX_COMMANDS: tuple[tuple[str, str], ...] = (
        ("/removeskill", "_cmd_removeskill"),
        ("/addskill", "_cmd_addskill"),
        ("/model", "_cmd_model"),
        ("/plugin", "_cmd_plugin"),
        ("/mcp", "_cmd_mcp"),
        ("/schedule", "_cmd_schedule"),
        ("/sessions", "_cmd_sessions_sub"),
        ("/session", "_cmd_session_sub"),
        ("/config", "_cmd_config"),
        ("/phone", "_cmd_phone"),
        ("/lockdown", "_cmd_lockdown"),
    )

    def __init__(
        self,
        agent: Agent,
        session_store: SessionStore | None = None,
        infra: InfraConfigStore | None = None,
    ) -> None:
        self._agent = agent
        self._session_store = session_store
        self._infra = infra

    @property
    def infra(self) -> InfraConfigStore:
        if self._infra is None:
            self._infra = InfraConfigStore()
        return self._infra

    async def try_handle(
        self,
        text: str,
        reply: ReplyFn,
        channel: str = "web",
        *,
        channel_ctx: ChannelContext | None = None,
    ) -> bool:
        lower = text.lower()
        ctx = CommandContext(text=text, reply=reply, channel=channel, channel_ctx=channel_ctx)

        handler_name = self._EXACT_COMMANDS.get(lower)
        if handler_name:
            await getattr(self, handler_name)(ctx)
            return True

        for prefix, handler_name in self._PREFIX_COMMANDS:
            if lower.startswith(prefix):
                await getattr(self, handler_name)(ctx)
                return True

        return False

    async def _cmd_new(self, ctx: CommandContext) -> None:
        await self._agent.new_session()
        if self._session_store:
            self._session_store.start_session(uuid.uuid4().hex[:12], model=cfg.copilot_model)
        await ctx.reply("New session started.")

    async def _cmd_model(self, ctx: CommandContext) -> None:
        parts = ctx.text.split(maxsplit=1)
        if len(parts) < 2:
            await ctx.reply(f"Current model: {cfg.copilot_model}\n\nUsage: /model <name>")
            return
        new_model = parts[1].strip()
        old_model = cfg.copilot_model
        cfg.write_env(COPILOT_MODEL=new_model)
        await self._agent.new_session()
        if self._session_store:
            self._session_store.start_session(uuid.uuid4().hex[:12], model=new_model)
        await ctx.reply(f"Model switched: {old_model} -> {new_model}\nNew session started.")

    async def _cmd_models(self, ctx: CommandContext) -> None:
        models = await self._agent.list_models()
        if not models:
            await ctx.reply("No models available.")
            return
        current = cfg.copilot_model
        lines = ["Available Models", ""]
        for m in models:
            marker = " *" if m["id"] == current else ""
            cost = f" ({m['billing_multiplier']}x)" if m.get("billing_multiplier", 1.0) != 1.0 else ""
            reasoning = f"  [reasoning: {', '.join(m['reasoning_efforts'])}]" if m.get("reasoning_efforts") else ""
            policy = m.get("policy", "enabled")
            if policy != "enabled":
                lines.append(f"  {m['id']}{marker}{cost}  ({policy})")
            else:
                lines.append(f"  {m['id']}{marker}{cost}{reasoning}")
        lines.append(f"\nCurrent: {current}\nUse /model <name> to switch.")
        await ctx.reply("\n".join(lines))

    async def _cmd_status(self, ctx: CommandContext) -> None:
        uptime_seconds = int(time.monotonic() - BOOT_TIME)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        sched = get_scheduler()
        tasks = sched.list_tasks()
        active_tasks = [t for t in tasks if t.enabled]
        total_reqs = sum(self._agent.request_counts.values())

        lines = [
            "System Status",
            f"  Model: {cfg.copilot_model}",
            f"  Uptime: {hours}h {minutes}m {seconds}s",
            f"  Total requests: {total_reqs}",
        ]
        for model, count in sorted(self._agent.request_counts.items()):
            lines.append(f"    {model}: {count}")
        if ctx.channel_ctx is not None:
            channels = ctx.channel_ctx.connected_channels
            lines.append(f"  Connected channels: {', '.join(sorted(channels)) or 'none'}")
            lines.append(f"  Conversation refs: {ctx.channel_ctx.conversation_refs_count}")
        lines.append(f"  Scheduled tasks: {len(active_tasks)} active / {len(tasks)} total")
        lines.append(f"  Data dir: {cfg.data_dir}")
        await ctx.reply("\n".join(lines))

    async def _cmd_skills(self, ctx: CommandContext) -> None:
        skills: list[str] = []
        if cfg.user_skills_dir.is_dir():
            for d in sorted(cfg.user_skills_dir.iterdir()):
                if d.is_dir() and (d / "SKILL.md").exists():
                    skills.append(d.name)
        lines = [f"Skills ({len(skills)}):"] + [f"  - {name}" for name in skills]
        if not skills:
            lines.append("  (none)")
        await ctx.reply("\n".join(lines))

    async def _cmd_session(self, ctx: CommandContext) -> None:
        lines = [
            "Session Info",
            f"  Active: {'yes' if self._agent.has_session else 'no'}",
            f"  Model: {cfg.copilot_model}",
            "  Playwright MCP: enabled",
        ]
        await ctx.reply("\n".join(lines))

    async def _cmd_channels(self, ctx: CommandContext) -> None:
        lines = ["Channel Configuration\n"]
        tg = self.infra.channels.telegram
        if tg.token:
            masked = tg.token[:8] + "..." + tg.token[-4:] if len(tg.token) > 12 else "***"
            lines.append(f"Telegram:\n  Token: {masked}\n  Whitelist: {tg.whitelist or '(none)'}")
        else:
            lines.append("Telegram: not configured")
        lines.append(f"\nBot Framework:\n  App ID: {cfg.bot_app_id[:8] + '...' if cfg.bot_app_id else 'not set'}")
        lines.append(f"  Tenant: {cfg.bot_app_tenant_id[:8] + '...' if cfg.bot_app_tenant_id else 'not set'}")
        lines.append(f"  Admin secret: {'set' if cfg.admin_secret else 'not set'}")
        if ctx.channel_ctx is not None:
            refs = ctx.channel_ctx.conversation_refs
            lines.append(f"\nActive Conversations ({len(refs)}):")
            for r in refs:
                user_name = r.user.name if r.user else "?"
                lines.append(f"  - {r.channel_id}: {user_name}")
        await ctx.reply("\n".join(lines))

    async def _cmd_clear(self, ctx: CommandContext) -> None:
        cleared = 0
        if cfg.memory_dir.is_dir():
            for f in cfg.memory_dir.rglob("*"):
                if f.is_file():
                    f.unlink()
                    cleared += 1
        await ctx.reply(f"Memory cleared ({cleared} files removed).")

    async def _cmd_addskill(self, ctx: CommandContext) -> None:
        parts = ctx.text.split(maxsplit=1)
        if len(parts) < 2:
            reg = get_skill_registry()
            try:
                catalog = await reg.fetch_catalog()
                available = [s for s in catalog if not s.installed]
                if available:
                    lines = [f"Available skills ({len(available)}):"]
                    for s in available:
                        desc = f" - {s.description}" if s.description else ""
                        lines.append(f"  {s.name}{desc}  [{s.source}]")
                    lines.append("\nUsage: /addskill <name>")
                else:
                    lines = ["All catalog skills already installed.", "Usage: /addskill <name>"]
            except Exception as exc:
                lines = [f"Failed to fetch catalog: {exc}", "Usage: /addskill <name>"]
            await ctx.reply("\n".join(lines))
            return
        name = parts[1].strip()
        reg = get_skill_registry()
        await ctx.reply(f"Installing skill '{name}'...")
        ok = await reg.install(name)
        await ctx.reply(f"Skill '{name}' installed." if ok else f"Failed to install skill '{name}'.")

    async def _cmd_removeskill(self, ctx: CommandContext) -> None:
        parts = ctx.text.split(maxsplit=1)
        if len(parts) < 2:
            reg = get_skill_registry()
            installed = reg.list_installed()
            if installed:
                lines = [f"Installed skills ({len(installed)}):"] + [f"  {s.name}" for s in installed]
                lines.append("\nUsage: /removeskill <name>")
            else:
                lines = ["No skills installed.", "Usage: /removeskill <name>"]
            await ctx.reply("\n".join(lines))
            return
        name = parts[1].strip()
        reg = get_skill_registry()
        removed = reg.remove(name)
        await ctx.reply(f"Skill '{name}' removed." if removed else f"Skill '{name}' not found.")

    async def _cmd_plugins(self, ctx: CommandContext) -> None:
        reg = get_plugin_registry()
        plugins = reg.list_plugins()
        if not plugins:
            await ctx.reply("No plugins found.")
            return
        lines = [f"Plugins ({len(plugins)}):"]
        for p in plugins:
            icon = "+" if p.get("enabled") else "-"
            desc = f" - {p['description']}" if p.get("description") else ""
            lines.append(f"  [{icon}] {p['id']}{desc} ({p.get('skill_count', 0)} skills)")
        lines.append("\nUsage: /plugin enable <id>, /plugin disable <id>")
        await ctx.reply("\n".join(lines))

    async def _cmd_plugin(self, ctx: CommandContext) -> None:
        parts = ctx.text.split()
        if len(parts) < 3:
            await ctx.reply("Usage: /plugin enable <id> or /plugin disable <id>")
            return
        action, plugin_id = parts[1].lower(), parts[2].strip()
        reg = get_plugin_registry()
        if action == "enable":
            result = reg.enable_plugin(plugin_id)
            await ctx.reply(f"Plugin '{plugin_id}' enabled." if result else f"Plugin '{plugin_id}' not found.")
        elif action == "disable":
            result = reg.disable_plugin(plugin_id)
            await ctx.reply(f"Plugin '{plugin_id}' disabled." if result else f"Plugin '{plugin_id}' not found.")
        else:
            await ctx.reply(f"Unknown action '{action}'.")

    async def _cmd_mcp(self, ctx: CommandContext) -> None:
        parts = ctx.text.split()
        store = McpConfigStore()
        if len(parts) == 1:
            servers = store.list_servers()
            if not servers:
                await ctx.reply("No MCP servers configured.")
                return
            lines = [f"MCP Servers ({len(servers)}):"]
            for s in servers:
                icon = "+" if s.get("enabled") else "-"
                builtin = " [builtin]" if s.get("builtin") else ""
                lines.append(f"  [{icon}] {s['name']} ({s.get('type', '?')}){builtin}")
                if s.get("description"):
                    lines.append(f"        {s['description']}")
            await ctx.reply("\n".join(lines))
            return

        action = parts[1].lower()
        if action == "add":
            if len(parts) < 4:
                await ctx.reply("Usage: /mcp add <name> <url>")
                return
            try:
                store.add_server(parts[2], "http", url=parts[3])
                await ctx.reply(f"MCP server '{parts[2]}' added. Start a /new session to activate.")
            except ValueError as exc:
                await ctx.reply(f"Error: {exc}")
        elif action == "remove":
            if len(parts) < 3:
                await ctx.reply("Usage: /mcp remove <name>")
                return
            try:
                ok = store.remove_server(parts[2])
                await ctx.reply(f"MCP server '{parts[2]}' removed." if ok else f"MCP server '{parts[2]}' not found.")
            except ValueError as exc:
                await ctx.reply(f"Error: {exc}")
        elif action in ("enable", "disable"):
            if len(parts) < 3:
                await ctx.reply(f"Usage: /mcp {action} <name>")
                return
            ok = store.set_enabled(parts[2], action == "enable")
            await ctx.reply(f"MCP server '{parts[2]}' {action}d." if ok else f"MCP server '{parts[2]}' not found.")
        else:
            await ctx.reply(f"Unknown MCP action '{action}'.")

    async def _cmd_schedules(self, ctx: CommandContext) -> None:
        sched = get_scheduler()
        tasks = sched.list_tasks()
        if not tasks:
            await ctx.reply("No scheduled tasks.\n\nUsage: /schedule add <cron> <prompt>")
            return
        lines = [f"Scheduled Tasks ({len(tasks)}):"]
        for t in tasks:
            icon = "+" if t.enabled else "-"
            schedule = t.cron or (f"once at {t.run_at}" if t.run_at else "?")
            lines.append(f"  [{icon}] {t.id} - {t.description}")
            lines.append(f"        Schedule: {schedule}  |  Last run: {t.last_run[:16] if t.last_run else 'never'}")
        await ctx.reply("\n".join(lines))

    async def _cmd_schedule(self, ctx: CommandContext) -> None:
        parts = ctx.text.split()
        if len(parts) < 2:
            await ctx.reply("Usage: /schedule add <cron> <prompt> or /schedule remove <id>")
            return
        action = parts[1].lower()
        sched = get_scheduler()
        if action == "add":
            if len(parts) < 8:
                await ctx.reply("Usage: /schedule add <min> <hour> <dom> <month> <dow> <prompt>")
                return
            cron = " ".join(parts[2:7])
            prompt = " ".join(parts[7:])
            try:
                task = sched.add(description=prompt[:60], prompt=prompt, cron=cron)
                await ctx.reply(f"Scheduled task created:\n  ID: {task.id}\n  Cron: {cron}\n  Prompt: {prompt}")
            except ValueError as exc:
                await ctx.reply(f"Error: {exc}")
        elif action == "remove":
            if len(parts) < 3:
                await ctx.reply("Usage: /schedule remove <id>")
                return
            ok = sched.remove(parts[2])
            await ctx.reply(f"Task '{parts[2]}' removed." if ok else f"Task '{parts[2]}' not found.")

    async def _cmd_sessions(self, ctx: CommandContext) -> None:
        if not self._session_store:
            await ctx.reply("Session store not available.")
            return
        sessions = self._session_store.list_sessions()
        if not sessions:
            await ctx.reply("No recorded sessions.")
            return
        stats = self._session_store.get_session_stats()
        lines = [f"Sessions ({stats['total_sessions']} total, {stats['total_messages']} messages)", ""]
        for s in sessions[:10]:
            started = s.get("started_at", "?")[:16]
            preview = s.get("first_message", "")[:50]
            lines.append(f"  {s['id']}  {started}  {s.get('model', '?')}  ({s.get('message_count', 0)} msgs)")
        if len(sessions) > 10:
            lines.append(f"  ... and {len(sessions) - 10} more")
        await ctx.reply("\n".join(lines))

    async def _cmd_sessions_sub(self, ctx: CommandContext) -> None:
        parts = ctx.text.split()
        if len(parts) >= 2 and parts[1].lower() == "clear":
            if not self._session_store:
                await ctx.reply("Session store not available.")
                return
            count = self._session_store.clear_all()
            await ctx.reply(f"All sessions cleared ({count} deleted).")
        else:
            await self._cmd_sessions(ctx)

    async def _cmd_session_sub(self, ctx: CommandContext) -> None:
        parts = ctx.text.split()
        if len(parts) >= 3 and parts[1].lower() == "delete":
            if not self._session_store:
                await ctx.reply("Session store not available.")
                return
            ok = self._session_store.delete_session(parts[2])
            await ctx.reply(f"Session '{parts[2]}' deleted." if ok else f"Session '{parts[2]}' not found.")
        else:
            await self._cmd_session(ctx)

    async def _cmd_profile(self, ctx: CommandContext) -> None:
        profile = load_profile()
        lines = [
            "Agent Profile",
            f"  Name: {profile.get('name') or '(not set)'}",
            f"  Location: {profile.get('location') or '(not set)'}",
            f"  Emotional state: {profile.get('emotional_state', 'neutral')}",
        ]
        prefs = profile.get("preferences", {})
        if prefs:
            lines.append("  Preferences:")
            for k, v in prefs.items():
                lines.append(f"    {k}: {v}")
        await ctx.reply("\n".join(lines))

    async def _cmd_config(self, ctx: CommandContext) -> None:
        parts = ctx.text.split(maxsplit=2)
        if len(parts) == 1:
            lines = [
                "Runtime Configuration",
                f"  Model: {cfg.copilot_model}",
                f"  Admin port: {cfg.admin_port}",
                f"  Bot port: {cfg.bot_port}",
                f"  Data dir: {cfg.data_dir}",
                f"  Admin secret: {'set' if cfg.admin_secret else 'not set'}",
                "\nUsage: /config <KEY> <VALUE>",
            ]
            await ctx.reply("\n".join(lines))
            return
        if len(parts) < 3:
            await ctx.reply("Usage: /config <KEY> <VALUE>")
            return
        key = parts[1].upper()
        allowed = {"COPILOT_MODEL", "ADMIN_PORT", "BOT_PORT", "VOICE_TARGET_NUMBER", "ACS_SOURCE_NUMBER"}
        if key not in allowed:
            await ctx.reply(f"Cannot set '{key}'. Allowed keys: {', '.join(sorted(allowed))}")
            return
        cfg.write_env(**{key: parts[2]})
        await ctx.reply(f"Config updated: {key} = {parts[2]}")

    async def _cmd_preflight(self, ctx: CommandContext) -> None:
        import aiohttp as _aiohttp

        base = f"http://127.0.0.1:{cfg.admin_port}"
        headers = {"Authorization": f"Bearer {cfg.admin_secret}"} if cfg.admin_secret else {}
        try:
            async with _aiohttp.ClientSession() as session:
                async with session.get(f"{base}/api/setup/preflight", headers=headers, timeout=_aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        await ctx.reply(f"Preflight check failed (HTTP {resp.status}).")
                        return
                    data = await resp.json()
        except Exception as exc:
            await ctx.reply(f"Cannot reach preflight endpoint: {exc}")
            return

        checks = data.get("checks", [])
        lines = [f"Preflight Checks ({data.get('status', '?').upper()})"]
        for c in checks:
            icon = "OK" if c.get("ok") else "!!"
            lines.append(f"  [{icon}] {c['check']}: {c.get('detail', '')}")
        await ctx.reply("\n".join(lines))

    async def _cmd_phone(self, ctx: CommandContext) -> None:
        parts = ctx.text.split(maxsplit=1)
        if len(parts) < 2:
            await ctx.reply(f"Current target number: {cfg.voice_target_number or '(not set)'}\n\nUsage: /phone <number>")
            return
        number = parts[1].strip()
        if not number.startswith("+"):
            await ctx.reply("Phone number must start with + country code.")
            return
        cfg.write_env(VOICE_TARGET_NUMBER=number)
        await ctx.reply(f"Voice target number set to {number}.")

    async def _cmd_call(self, ctx: CommandContext) -> None:
        import aiohttp as _aiohttp

        target = cfg.voice_target_number
        if not target:
            await ctx.reply("No target number configured. Use /phone <number> first.")
            return
        base = f"http://127.0.0.1:{cfg.admin_port}"
        headers = {"Authorization": f"Bearer {cfg.admin_secret}"} if cfg.admin_secret else {}
        try:
            async with _aiohttp.ClientSession() as session:
                async with session.post(f"{base}/api/voice/call", json={"target_number": target}, headers=headers, timeout=_aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        await ctx.reply(f"Calling {target}...")
                    else:
                        await ctx.reply(f"Call failed: {data.get('error', f'HTTP {resp.status}')}")
        except Exception as exc:
            await ctx.reply(f"Call failed: {exc}")

    async def _cmd_change(self, ctx: CommandContext) -> None:
        if not self._session_store:
            await ctx.reply("Session store not available.")
            return
        sessions = self._session_store.list_sessions()
        if not sessions:
            await ctx.reply("No sessions to switch to. Use /new to start one.")
            return
        lines = ["Recent Sessions:", ""]
        for i, s in enumerate(sessions[:5], 1):
            started = s.get("started_at", "?")[:16]
            lines.append(f"  {i}. {started}  {s.get('model', '?')}  ({s.get('message_count', 0)} msgs)")
            lines.append(f"     ID: {s['id']}")
        await ctx.reply("\n".join(lines))

    async def _cmd_lockdown(self, ctx: CommandContext) -> None:
        parts = ctx.text.split()
        if len(parts) < 2:
            state = "ENABLED" if cfg.lockdown_mode else "disabled"
            await ctx.reply(f"Lock Down Mode: {state}\n\nUsage: /lockdown on | /lockdown off")
            return
        action = parts[1].lower()
        if action not in ("on", "off"):
            await ctx.reply("Usage: /lockdown on | /lockdown off")
            return
        if action == "on":
            if cfg.lockdown_mode:
                await ctx.reply("Lock Down Mode is already enabled.")
                return
            cfg.write_env(LOCKDOWN_MODE="1", TUNNEL_RESTRICTED="1")
            from ..services.azure import AzureCLI
            az = AzureCLI()
            az.ok("logout")
            az.invalidate_cache("account", "show")
            await ctx.reply("Lock Down Mode ENABLED\n\n  - Azure CLI logged out\n  - Admin panel disabled")
        else:
            if not cfg.lockdown_mode:
                await ctx.reply("Lock Down Mode is already disabled.")
                return
            cfg.write_env(LOCKDOWN_MODE="", TUNNEL_RESTRICTED="")
            await ctx.reply("Lock Down Mode DISABLED\n\n  - Admin panel re-enabled")

    async def _cmd_help(self, ctx: CommandContext) -> None:
        lines = [
            "Available Commands",
            "",
            "  /new, /model <name>, /models, /status, /session, /config",
            "  /skills, /addskill <name>, /removeskill <name>",
            "  /plugins, /plugin enable|disable <id>",
            "  /mcp, /mcp add|remove|enable|disable <name>",
            "  /schedules, /schedule add|remove",
            "  /sessions, /session delete <id>, /sessions clear",
            "  /change, /profile, /channels, /clear",
            "  /phone <number>, /call, /preflight, /lockdown, /help",
        ]
        await ctx.reply("\n".join(lines))
