"""Scheduler CRUD API routes -- /api/schedules/*."""

from __future__ import annotations

from dataclasses import asdict

from aiohttp import web

from ...scheduler import Scheduler


class SchedulerRoutes:
    """REST handler for scheduled tasks."""

    def __init__(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler

    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get("/api/schedules", self._list)
        router.add_post("/api/schedules", self._create)
        router.add_put("/api/schedules/{task_id}", self._update)
        router.add_delete("/api/schedules/{task_id}", self._delete)

    async def _list(self, _req: web.Request) -> web.Response:
        tasks = self._scheduler.list_tasks()
        return web.json_response([asdict(t) for t in tasks])

    async def _create(self, req: web.Request) -> web.Response:
        data = await req.json()
        try:
            task = self._scheduler.add(
                description=data.get("description") or data.get("name", ""),
                prompt=data.get("prompt", ""),
                cron=data.get("cron") or data.get("schedule"),
                run_at=data.get("run_at"),
            )
            return web.json_response({"status": "ok", "task": asdict(task)})
        except ValueError as exc:
            return web.json_response(
                {"status": "error", "message": str(exc)}, status=400
            )

    async def _update(self, req: web.Request) -> web.Response:
        task_id = req.match_info["task_id"]
        data = await req.json()
        # Normalise frontend field aliases
        if "schedule" in data and "cron" not in data:
            data["cron"] = data.pop("schedule")
        if "name" in data and "description" not in data:
            data["description"] = data.pop("name")
        try:
            task = self._scheduler.update(task_id, **data)
        except ValueError as exc:
            return web.json_response(
                {"status": "error", "message": str(exc)}, status=400
            )
        if not task:
            return web.json_response(
                {"status": "error", "message": "Task not found"}, status=404
            )
        return web.json_response({"status": "ok", "task": asdict(task)})

    async def _delete(self, req: web.Request) -> web.Response:
        task_id = req.match_info["task_id"]
        removed = self._scheduler.remove(task_id)
        if not removed:
            return web.json_response(
                {"status": "error", "message": "Task not found"}, status=404
            )
        return web.json_response({"status": "ok"})
