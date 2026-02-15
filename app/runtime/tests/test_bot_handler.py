"""Tests for Bot handler and related helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.runtime.messaging.bot import Bot, _BotChannelContext, _is_authorized, _reply


class TestBotChannelContext:
    def test_conversation_refs_count(self) -> None:
        store = MagicMock()
        store.count = 3
        ctx = _BotChannelContext(store)
        assert ctx.conversation_refs_count == 3

    def test_connected_channels(self) -> None:
        ref1 = MagicMock()
        ref1.channel_id = "telegram"
        ref2 = MagicMock()
        ref2.channel_id = "webchat"
        ref3 = MagicMock()
        ref3.channel_id = None
        store = MagicMock()
        store.get_all.return_value = [ref1, ref2, ref3]
        ctx = _BotChannelContext(store)
        channels = ctx.connected_channels
        assert "telegram" in channels
        assert "webchat" in channels
        assert "unknown" in channels

    def test_conversation_refs(self) -> None:
        refs = [MagicMock(), MagicMock()]
        store = MagicMock()
        store.get_all.return_value = refs
        ctx = _BotChannelContext(store)
        assert ctx.conversation_refs == refs


class TestIsAuthorized:
    def test_non_telegram_always_authorized(self) -> None:
        turn_ctx = MagicMock()
        turn_ctx.activity.channel_id = "webchat"
        with patch("app.runtime.messaging.bot.cfg") as mock_cfg:
            mock_cfg.telegram_whitelist = ["123"]
            assert _is_authorized(turn_ctx) is True

    def test_telegram_no_whitelist(self) -> None:
        turn_ctx = MagicMock()
        turn_ctx.activity.channel_id = "telegram"
        with patch("app.runtime.messaging.bot.cfg") as mock_cfg:
            mock_cfg.telegram_whitelist = []
            assert _is_authorized(turn_ctx) is True

    def test_telegram_authorized(self) -> None:
        turn_ctx = MagicMock()
        turn_ctx.activity.channel_id = "telegram"
        turn_ctx.activity.from_property.id = "user-123"
        with patch("app.runtime.messaging.bot.cfg") as mock_cfg:
            mock_cfg.telegram_whitelist = ["user-123", "user-456"]
            assert _is_authorized(turn_ctx) is True

    def test_telegram_blocked(self) -> None:
        turn_ctx = MagicMock()
        turn_ctx.activity.channel_id = "telegram"
        turn_ctx.activity.from_property.id = "user-999"
        with patch("app.runtime.messaging.bot.cfg") as mock_cfg:
            mock_cfg.telegram_whitelist = ["user-123"]
            assert _is_authorized(turn_ctx) is False

    def test_telegram_no_from_property(self) -> None:
        turn_ctx = MagicMock()
        turn_ctx.activity.channel_id = "telegram"
        turn_ctx.activity.from_property = None
        with patch("app.runtime.messaging.bot.cfg") as mock_cfg:
            mock_cfg.telegram_whitelist = ["user-123"]
            assert _is_authorized(turn_ctx) is False

    def test_case_insensitive_channel(self) -> None:
        turn_ctx = MagicMock()
        turn_ctx.activity.channel_id = "Telegram"
        turn_ctx.activity.from_property.id = "user-123"
        with patch("app.runtime.messaging.bot.cfg") as mock_cfg:
            mock_cfg.telegram_whitelist = ["user-123"]
            assert _is_authorized(turn_ctx) is True


class TestReply:
    @pytest.mark.asyncio
    async def test_reply_sends_activity(self) -> None:
        ctx = AsyncMock()
        await _reply(ctx, "Hello!")
        ctx.send_activity.assert_awaited_once()
        activity = ctx.send_activity.call_args[0][0]
        assert activity.text == "Hello!"
        assert activity.text_format == "plain"
