"""Bot Framework ActivityHandler -- routes channel messages to the Agent.

Uses background processing + proactive messaging so the Bot Framework
webhook returns within the 15-second timeout.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from botbuilder.core import ActivityHandler, BotFrameworkAdapter, TurnContext
from botbuilder.schema import Activity, ActivityTypes, ChannelAccount

from ..agent.agent import Agent
from ..config.settings import cfg
from ..media import build_media_prompt, download_attachment
from ..state.memory import get_memory
from ..state.profile import log_interaction
from ..state.session_store import SessionStore
from .commands import CommandDispatcher
from .message_processor import MessageProcessor
from .proactive import ConversationReferenceStore

logger = logging.getLogger(__name__)


class _BotChannelContext:
    def __init__(self, store: ConversationReferenceStore) -> None:
        self._store = store

    @property
    def conversation_refs_count(self) -> int:
        return self._store.count

    @property
    def connected_channels(self) -> set[str]:
        return {r.channel_id or "unknown" for r in self._store.get_all()}

    @property
    def conversation_refs(self) -> list[Any]:
        return self._store.get_all()


class Bot(ActivityHandler):
    def __init__(self, agent: Agent, conv_store: ConversationReferenceStore) -> None:
        self._agent = agent
        self._conv_store = conv_store
        self.adapter: BotFrameworkAdapter | None = None
        self._memory = get_memory()
        self.session_store = SessionStore()
        self._commands = CommandDispatcher(agent, self.session_store)
        self._processor = MessageProcessor(
            agent,
            self.adapter,
            self._memory,
            self.session_store,
        )

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        if not _is_authorized(turn_context):
            await _reply(turn_context, "You are not authorized to use this bot.")
            return

        ref = TurnContext.get_conversation_reference(turn_context.activity)
        self._conv_store.upsert(ref)

        user_text = (turn_context.activity.text or "").strip()
        attachments = turn_context.activity.attachments or []
        media_attachments = [
            a for a in attachments
            if a.content_type and not a.content_type.startswith("application/vnd.microsoft")
        ]

        if not user_text and not media_attachments:
            return

        channel = (turn_context.activity.channel_id or "unknown").lower()

        async def reply_fn(text: str) -> None:
            await _reply(turn_context, text)

        ctx = _BotChannelContext(self._conv_store)
        if await self._commands.try_handle(user_text, reply_fn, channel, channel_ctx=ctx):
            return

        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        saved_files = [
            info for att in media_attachments
            if (info := await download_attachment(att, turn_context.activity.channel_id))
        ]
        prompt = build_media_prompt(user_text, saved_files)

        self._memory.record("user", user_text)
        self.session_store.record("user", user_text, channel=channel)
        log_interaction("user", channel=channel)

        self._processor.adapter = self.adapter
        asyncio.create_task(self._processor.process(ref, prompt, channel))

    async def on_members_added_activity(
        self,
        members_added: list[ChannelAccount],
        turn_context: TurnContext,
    ) -> None:
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                ref = TurnContext.get_conversation_reference(turn_context.activity)
                self._conv_store.upsert(ref)
                await turn_context.send_activity(
                    "Hello! I'm your autonomous copilot. Send any message to begin."
                )


async def _reply(ctx: TurnContext, text: str) -> None:
    await ctx.send_activity(
        Activity(type=ActivityTypes.message, text=text, text_format="plain")
    )


def _is_authorized(turn_context: TurnContext) -> bool:
    channel = (turn_context.activity.channel_id or "").lower()
    if channel != "telegram" or not cfg.telegram_whitelist:
        return True
    sender_id = (
        turn_context.activity.from_property.id if turn_context.activity.from_property else ""
    )
    if sender_id not in cfg.telegram_whitelist:
        logger.warning("Blocked Telegram user %s (not in whitelist)", sender_id)
        return False
    return True
