"""Custom tools exposed to the Copilot agent."""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request

from copilot import define_tool
from pydantic import BaseModel, Field

from ..config.settings import cfg
from ..messaging.cards import CARD_TOOLS

logger = logging.getLogger(__name__)


class ScheduleTaskParams(BaseModel):
    description: str = Field(description="Human-readable description of the task")
    prompt: str = Field(description="The prompt to send to the agent when this task fires")
    cron: str | None = Field(
        default=None,
        description=(
            "Cron expression for recurring tasks (minute hour day month weekday). "
            "Minimum interval is every 1 hour. "
            "Example: '0 9 * * *' for every day at 09:00 UTC."
        ),
    )
    run_at: str | None = Field(
        default=None,
        description="ISO datetime for one-shot tasks (e.g. '2026-02-07T14:00:00')",
    )


class CancelTaskParams(BaseModel):
    task_id: str = Field(description="ID of the scheduled task to cancel")


class MakeCallParams(BaseModel):
    prompt: str | None = Field(
        default=None,
        description="Optional custom prompt / instructions for the voice AI agent.",
    )
    opening_message: str | None = Field(
        default=None,
        description="Optional opening message the AI should speak when the call connects.",
    )


class SearchMemoriesParams(BaseModel):
    query: str = Field(
        description="Natural language search query to find relevant memories.",
    )
    top: int = Field(default=5, description="Maximum number of results to return (1-10).")


@define_tool(
    description=(
        "Schedule a future task. Provide either a cron expression for recurring "
        "tasks (minimum every 1 hour) or a run_at datetime for one-shot tasks."
    )
)
def schedule_task(params: ScheduleTaskParams) -> dict:
    from ..scheduler import get_scheduler

    scheduler = get_scheduler()
    logger.info(
        "[schedule_task] called: desc=%r, cron=%r, run_at=%r, prompt=%r",
        params.description, params.cron, params.run_at, params.prompt[:80] if params.prompt else None,
    )
    try:
        task = scheduler.add(
            description=params.description,
            prompt=params.prompt,
            cron=params.cron,
            run_at=params.run_at,
        )
        logger.info(
            "[schedule_task] created task id=%s, run_at=%s, cron=%s, notify_cb=%s",
            task.id, task.run_at, task.cron,
            "SET" if scheduler._notify else "NOT SET",
        )
        return {"id": task.id, "description": task.description, "status": "scheduled"}
    except ValueError as exc:
        logger.warning("[schedule_task] rejected: %s", exc)
        return {"error": str(exc)}


@define_tool(description="Cancel a scheduled task by ID.")
def cancel_task(params: CancelTaskParams) -> str:
    from ..scheduler import get_scheduler

    scheduler = get_scheduler()
    return f"Task {params.task_id} cancelled." if scheduler.remove(params.task_id) else f"Task {params.task_id} not found."


@define_tool(description="List all scheduled tasks with their ID, description, schedule, and status.")
def list_scheduled_tasks() -> list[dict]:
    from ..scheduler import get_scheduler

    return [
        {
            "id": t.id,
            "description": t.description,
            "cron": t.cron,
            "run_at": t.run_at,
            "enabled": t.enabled,
            "last_run": t.last_run,
        }
        for t in get_scheduler().list_tasks()
    ]


@define_tool(
    description=(
        "Initiate an outbound voice call to the user. ALWAYS call this tool "
        "when the user asks to be called -- the target phone number is managed "
        "internally and you do not need to ask the user for it."
    )
)
def make_voice_call(params: MakeCallParams) -> dict:
    target = cfg.voice_target_number
    if not target:
        return {
            "status": "error",
            "message": (
                "No target phone number configured yet. "
                "Ask the user to run: /phone <number>  (e.g. /phone +14155551234)"
            ),
        }
    url = f"http://127.0.0.1:{cfg.admin_port}/api/voice/call"
    body: dict[str, str] = {"number": target}
    if params.prompt:
        body["prompt"] = params.prompt
    if params.opening_message:
        body["opening_message"] = params.opening_message
    payload = json.dumps(body).encode("utf-8")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if cfg.admin_secret:
        headers["Authorization"] = f"Bearer {cfg.admin_secret}"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    def _fire() -> None:
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                logger.info("Voice call API responded: %s", resp.read().decode()[:200])
        except Exception as exc:
            logger.error("Voice call API request failed: %s", exc)

    threading.Thread(target=_fire, daemon=True).start()
    return {"status": "ok", "message": "Call triggered"}


@define_tool(
    description=(
        "Search through indexed memories using Azure AI Search with vector "
        "embeddings. Only works when Foundry IQ is enabled."
    )
)
def search_memories_tool(params: SearchMemoriesParams) -> dict:
    from ..services.foundry_iq import search_memories
    from ..state.foundry_iq_config import get_foundry_iq_config

    config = get_foundry_iq_config()
    if not config.enabled or not config.is_configured:
        return {"status": "skipped", "message": "Foundry IQ is not enabled."}

    try:
        top = min(max(params.top, 1), 10)
        data = search_memories(params.query, top, config)
        if data.get("status") == "ok" and data.get("results"):
            formatted = [
                {
                    "title": r.get("title", ""),
                    "content": r.get("content", ""),
                    "source_type": r.get("source_type", ""),
                    "date": r.get("date", ""),
                }
                for r in data["results"]
            ]
            return {"status": "ok", "results": formatted, "count": len(formatted)}
        return {"status": "ok", "results": [], "count": 0, "message": "No matching memories found."}
    except Exception as exc:
        return {"status": "error", "message": f"Memory search failed: {exc}"}


ALL_TOOLS = [schedule_task, cancel_task, list_scheduled_tasks, make_voice_call] + CARD_TOOLS


def get_all_tools() -> list:
    from ..state.foundry_iq_config import get_foundry_iq_config

    tools = list(ALL_TOOLS)
    try:
        fiq = get_foundry_iq_config()
        if fiq.enabled and fiq.is_configured:
            tools.append(search_memories_tool)
    except Exception:
        pass
    return tools
