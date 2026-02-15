"""Workspace file browser -- /api/workspace/*."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aiohttp import web

_MAX_PREVIEW_SIZE = 512 * 1024


class WorkspaceHandler:
    """Sandboxed file browser over the data directory."""

    ROOTS: dict[str, Path] = {
        "data": Path(os.getenv("OCTOCLAW_DATA_DIR", str(Path.home() / ".octoclaw"))),
    }

    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get("/api/workspace/list", self.list_dir)
        router.add_get("/api/workspace/read", self.read_file)

    async def list_dir(self, req: web.Request) -> web.Response:
        rel = req.query.get("path", "data") or "data"
        target = self._resolve(rel)
        if target is None or not target.is_dir():
            return web.json_response(
                {"status": "error", "message": "Invalid directory"}, status=400
            )

        root_key, root = self._root_for(rel)
        try:
            children = sorted(
                target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
            entries = [
                self._entry(c, root_key, root)
                for c in children
                if c.name != "__pycache__"
            ]
        except PermissionError:
            return web.json_response(
                {"status": "error", "message": "Permission denied"}, status=403
            )
        return web.json_response({"status": "ok", "path": rel, "entries": entries})

    async def read_file(self, req: web.Request) -> web.Response:
        rel = req.query.get("path", "")
        if not rel:
            return web.json_response(
                {"status": "error", "message": "path required"}, status=400
            )

        target = self._resolve(rel)
        if target is None or not target.is_file():
            return web.json_response(
                {"status": "error", "message": "File not found"}, status=404
            )

        try:
            size = target.stat().st_size
        except OSError:
            return web.json_response(
                {"status": "error", "message": "Cannot stat file"}, status=500
            )

        if self._is_binary(target):
            return web.json_response(
                {"status": "ok", "path": rel, "binary": True, "size": size, "content": None}
            )

        truncated = size > _MAX_PREVIEW_SIZE
        try:
            content = target.read_text(errors="replace")
            if truncated:
                content = content[:_MAX_PREVIEW_SIZE]
        except OSError as exc:
            return web.json_response(
                {"status": "error", "message": str(exc)}, status=500
            )

        return web.json_response({
            "status": "ok",
            "path": rel,
            "binary": False,
            "size": size,
            "truncated": truncated,
            "content": content,
        })

    def _resolve(self, rel: str) -> Path | None:
        if not rel or rel == ".":
            return None
        root_key = rel.split("/", 1)[0]
        root = self.ROOTS.get(root_key)
        if root is None:
            return None
        sub = rel.split("/", 1)[1] if "/" in rel else ""
        try:
            target = (root / sub).resolve()
        except (ValueError, OSError):
            return None
        if not str(target).startswith(str(root.resolve())):
            return None
        return target

    def _root_for(self, rel: str) -> tuple[str, Path]:
        key = rel.split("/", 1)[0]
        return key, self.ROOTS[key]

    @staticmethod
    def _entry(child: Path, root_key: str, root: Path) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "name": child.name,
            "path": root_key + "/" + str(child.relative_to(root)),
            "is_dir": child.is_dir(),
        }
        if not child.is_dir():
            try:
                entry["size"] = child.stat().st_size
            except OSError:
                entry["size"] = 0
        return entry

    @staticmethod
    def _is_binary(path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                return b"\x00" in f.read(8192)
        except OSError:
            return True
