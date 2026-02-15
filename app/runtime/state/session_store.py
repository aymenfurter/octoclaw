"""Session history store -- one JSON file per session."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config.settings import cfg

logger = logging.getLogger(__name__)

ARCHIVAL_OPTIONS: dict[str, int | None] = {
    "24h": 86_400,
    "7d": 604_800,
    "30d": 2_592_000,
    "never": None,
}


@dataclass
class ToolCall:
    name: str = ""
    arguments: str = ""
    result: str = ""


@dataclass
class SessionMessage:
    role: str = ""
    content: str = ""
    timestamp: float = 0.0
    channel: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class Session:
    id: str = ""
    messages: list[SessionMessage] = field(default_factory=list)
    model: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    title: str = ""


class SessionStore:
    """Directory-backed session store with one JSON file per session."""

    def __init__(self, directory: Path | None = None) -> None:
        self._dir = directory or cfg.sessions_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._current_id: str = ""
        self._pending_model: str = ""
        self._policy: str = "7d"
        self._purge_empty()
        self._apply_archival()

    @property
    def current_session_id(self) -> str:
        return self._current_id

    @current_session_id.setter
    def current_session_id(self, value: str) -> None:
        self._current_id = value

    def _path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.json"

    def _load(self, session_id: str) -> Session | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            msgs = [
                SessionMessage(
                    role=m.get("role", ""),
                    content=m.get("content", ""),
                    timestamp=m.get("timestamp", 0),
                    channel=m.get("channel", ""),
                    tool_calls=[ToolCall(**tc) for tc in m.get("tool_calls", [])],
                )
                for m in data.get("messages", [])
            ]
            return Session(
                id=data.get("id", session_id),
                messages=msgs,
                model=data.get("model", ""),
                created_at=data.get("created_at", 0),
                updated_at=data.get("updated_at", 0),
                title=data.get("title", ""),
            )
        except (json.JSONDecodeError, OSError):
            return None

    def _save_session(self, session: Session) -> None:
        session.updated_at = time.time()
        self._path(session.id).write_text(
            json.dumps(asdict(session), indent=2, default=str) + "\n"
        )

    def record(
        self,
        role: str,
        content: str,
        *,
        channel: str = "",
        tool_calls: list[ToolCall] | None = None,
    ) -> None:
        if not self._current_id:
            return
        session = self._load(self._current_id) or Session(
            id=self._current_id,
            created_at=time.time(),
            model=self._pending_model,
        )
        session.messages.append(
            SessionMessage(
                role=role,
                content=content,
                timestamp=time.time(),
                channel=channel,
                tool_calls=tool_calls or [],
            )
        )
        self._save_session(session)

    def start_session(self, session_id: str, model: str = "") -> None:
        self._current_id = session_id
        self._pending_model = model
        existing = self._load(session_id)
        if existing and existing.messages:
            existing.model = model
            self._save_session(existing)

    def list_sessions(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for path in self._dir.glob("*.json"):
            session = self._load(path.stem)
            if not session or not session.messages:
                if path.exists():
                    path.unlink()
                continue
            result.append({
                "id": session.id,
                "title": session.title or self._derive_title(session),
                "model": session.model,
                "message_count": len(session.messages),
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            })
        result.sort(key=lambda s: s["updated_at"] or s["created_at"], reverse=True)
        return result

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self._load(session_id)
        if not session:
            return None
        return asdict(session)

    def delete_session(self, session_id: str) -> bool:
        path = self._path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear_all(self) -> int:
        count = 0
        for path in self._dir.glob("*.json"):
            path.unlink()
            count += 1
        return count

    def get_session_stats(self) -> dict[str, Any]:
        sessions = self.list_sessions()
        total_messages = sum(s["message_count"] for s in sessions)
        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "archival_policy": self._policy,
        }

    def get_archival_policy(self) -> str:
        return self._policy

    def set_archival_policy(self, policy: str) -> None:
        if policy not in ARCHIVAL_OPTIONS:
            raise ValueError(f"Invalid policy: {policy}")
        self._policy = policy
        self._apply_archival()

    def _purge_empty(self) -> None:
        """Remove session files that contain zero messages."""
        for path in self._dir.glob("*.json"):
            session = self._load(path.stem)
            if session and not session.messages:
                path.unlink()

    def _apply_archival(self) -> None:
        max_age = ARCHIVAL_OPTIONS.get(self._policy)
        if max_age is None:
            return
        cutoff = time.time() - max_age
        for path in self._dir.glob("*.json"):
            session = self._load(path.stem)
            if session and session.updated_at and session.updated_at < cutoff:
                path.unlink()

    @staticmethod
    def _derive_title(session: Session) -> str:
        for msg in session.messages:
            if msg.role == "user" and msg.content:
                return msg.content[:60]
        return f"Session {session.id[:8]}"
