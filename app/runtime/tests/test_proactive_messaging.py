"""Tests for proactive messaging -- ConversationReferenceStore and helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from botbuilder.schema import (
    ChannelAccount,
    ConversationAccount,
    ConversationReference,
)

from app.runtime.messaging.proactive import (
    ConversationReferenceStore,
    _deserialize_ref,
    _serialize_ref,
)


def _make_ref(
    channel_id: str = "webchat",
    user_id: str = "user1",
    user_name: str = "Alice",
    bot_id: str = "bot1",
    service_url: str = "https://smba.trafficmanager.net",
) -> ConversationReference:
    return ConversationReference(
        activity_id="act1",
        user=ChannelAccount(id=user_id, name=user_name),
        bot=ChannelAccount(id=bot_id, name="Bot"),
        conversation=ConversationAccount(id="conv1", name="Main"),
        channel_id=channel_id,
        locale="en-us",
        service_url=service_url,
    )


class TestSerializeDeserialize:
    def test_roundtrip(self) -> None:
        ref = _make_ref()
        data = _serialize_ref(ref)
        restored = _deserialize_ref(data)
        assert restored.channel_id == "webchat"
        assert restored.user.id == "user1"
        assert restored.user.name == "Alice"
        assert restored.bot.id == "bot1"
        assert restored.conversation.id == "conv1"
        assert restored.service_url == "https://smba.trafficmanager.net"

    def test_serialize_structure(self) -> None:
        ref = _make_ref()
        data = _serialize_ref(ref)
        assert data["channel_id"] == "webchat"
        assert data["user"]["id"] == "user1"
        assert data["bot"]["id"] == "bot1"

    def test_deserialize_minimal(self) -> None:
        data = {"channel_id": "telegram"}
        ref = _deserialize_ref(data)
        assert ref.channel_id == "telegram"
        assert ref.user is None
        assert ref.bot is None

    def test_serialize_none_user(self) -> None:
        ref = ConversationReference(channel_id="test")
        data = _serialize_ref(ref)
        assert data["user"] is None


class TestConversationReferenceStore:
    def test_empty_store(self, data_dir: Path) -> None:
        path = data_dir / "refs.json"
        store = ConversationReferenceStore(path=path)
        assert store.is_empty
        assert store.count == 0
        assert store.get_all() == []

    def test_upsert_and_get_all(self, data_dir: Path) -> None:
        path = data_dir / "refs.json"
        store = ConversationReferenceStore(path=path)
        ref = _make_ref()
        store.upsert(ref)
        assert store.count == 1
        refs = store.get_all()
        assert len(refs) == 1
        assert refs[0].user.id == "user1"

    def test_upsert_same_key_updates(self, data_dir: Path) -> None:
        path = data_dir / "refs.json"
        store = ConversationReferenceStore(path=path)
        store.upsert(_make_ref(user_name="Alice"))
        store.upsert(_make_ref(user_name="Alice2"))
        assert store.count == 1
        refs = store.get_all()
        assert refs[0].user.name == "Alice2"

    def test_multiple_channels(self, data_dir: Path) -> None:
        path = data_dir / "refs.json"
        store = ConversationReferenceStore(path=path)
        store.upsert(_make_ref(channel_id="webchat", user_id="u1"))
        store.upsert(_make_ref(channel_id="telegram", user_id="u2"))
        assert store.count == 2

    def test_remove(self, data_dir: Path) -> None:
        path = data_dir / "refs.json"
        store = ConversationReferenceStore(path=path)
        store.upsert(_make_ref(channel_id="webchat", user_id="u1"))
        store.remove("webchat:u1")
        assert store.is_empty

    def test_remove_nonexistent(self, data_dir: Path) -> None:
        path = data_dir / "refs.json"
        store = ConversationReferenceStore(path=path)
        store.remove("nonexistent")
        assert store.is_empty

    def test_persistence(self, data_dir: Path) -> None:
        path = data_dir / "refs.json"
        store1 = ConversationReferenceStore(path=path)
        store1.upsert(_make_ref())
        store2 = ConversationReferenceStore(path=path)
        assert store2.count == 1

    def test_corrupt_file(self, data_dir: Path) -> None:
        path = data_dir / "refs.json"
        path.write_text("{bad json!!!")
        store = ConversationReferenceStore(path=path)
        assert store.is_empty
