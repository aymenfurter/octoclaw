"""Server route handlers."""

from __future__ import annotations

from .env_routes import EnvironmentRoutes
from .foundry_iq_routes import FoundryIQRoutes
from .mcp_routes import McpRoutes
from .plugin_routes import PluginRoutes
from .proactive_routes import ProactiveRoutes
from .profile_routes import ProfileRoutes
from .sandbox_routes import SandboxRoutes
from .scheduler_routes import SchedulerRoutes
from .session_routes import SessionRoutes
from .skill_routes import SkillRoutes

__all__ = [
    "EnvironmentRoutes",
    "FoundryIQRoutes",
    "McpRoutes",
    "PluginRoutes",
    "ProactiveRoutes",
    "ProfileRoutes",
    "SandboxRoutes",
    "SchedulerRoutes",
    "SessionRoutes",
    "SkillRoutes",
]
