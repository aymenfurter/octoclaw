"""Tests for proactive messaging helpers and ConversationReferenceStore."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botbuilder.schema import ChannelAccount, ConversationAccount, ConversationReference

from app.runtime.messaging.proactive import (
    ConversationReferenceStore,
    _channel_account,
    _conversation_account,
    _deserialize_ref,
    _serialize_ref,
)


class TestChannelAccount:
    def test_with_data(self) -> None:
        result = _channel_account({"id": "user-1", "name": "Alice"})
        assert result is not None
        assert result.id == "user-1"
        assert result.name == "Alice"

    def test_none(self) -> None:
        assert _channel_account(None) is None

    def test_empty(self) -> None:
        # Empty dict is falsy, returns None
        assert _channel_account({}) is None


class TestConversationAccount:
    def test_with_data(self) -> None:
        result = _conversation_account({"id": "conv-1", "name": "Chat"})
        assert result is not None
        assert result.id == "conv-1"

    def test_none(self) -> None:
        assert _conversation_account(None) is None

    def test_filters_none_values(self) -> None:
        result = _conversation_account({"id": "conv-1", "name": None})
        assert result is not None
        assert result.id == "conv-1"


class TestSerializeDeserialize:
    def test_roundtrip(self) -> None:
        ref = ConversationReference(
            activity_id="a1",
            user=ChannelAccount(id="u1", name="User"),
            bot=ChannelAccount(id="b1", name="Bot"),
            conversation=ConversationAccount(id="c1", name="Conv"),
            channel_id="webchat",
            locale="en-US",
            service_url="https://example.com",
        )
        serialized = _serialize_ref(ref)
        deserialized = _deserialize_ref(serialized)
        assert deserialized.activity_id == "a1"
        assert deserialized.user.id == "u1"
        assert deserialized.bot.id == "b1"
        assert deserialized.channel_id == "webchat"
        assert deserialized.service_url == "https://example.com"

    def test_serialize_none_user(self) -> None:
        ref = ConversationReference(user=None, bot=None, conversation=None)
        serialized = _serialize_ref(ref)
        assert serialized["user"] is None
        assert serialized["bot"] is None

    def test_deserialize_minimal(self) -> None:
        data = {"channel_id": "test"}
        ref = _deserialize_ref(data)
        assert ref.channel_id == "test"
        assert ref.user is None


class TestConversationReferenceStore:
    def test_empty_store(self, tmp_path: Path) -> None:
        store = ConversationReferenceStore(path=tmp_path / "refs.json")
        assert store.is_empty
        assert store.count == 0
        assert store.get_all() == []

    def test_upsert_and_get(self, tmp_path: Path) -> None:
        store = ConversationReferenceStore(path=tmp_path / "refs.json")
        ref = ConversationReference(
            user=ChannelAccount(id="u1", name="User"),
            channel_id="webchat",
        )
        store.upsert(ref)
        assert store.count == 1
        assert not store.is_empty
        all_refs = store.get_all()
        assert len(all_refs) == 1
        assert all_refs[0].user.id == "u1"

    def test_upsert_same_key(self, tmp_path: Path) -> None:
        store = ConversationReferenceStore(path=tmp_path / "refs.json")
        ref1 = ConversationReference(
            user=ChannelAccount(id="u1", name="V1"),
            channel_id="webchat",
        )
        ref2 = ConversationReference(
            user=ChannelAccount(id="u1", name="V2"),
            channel_id="webchat",
        )
        store.upsert(ref1)
        store.upsert(ref2)
        assert store.count == 1
        assert store.get_all()[0].user.name == "V2"

    def test_remove(self, tmp_path: Path) -> None:
        store = ConversationReferenceStore(path=tmp_path / "refs.json")
        ref = ConversationReference(
            user=ChannelAccount(id="u1"),
            channel_id="webchat",
        )
        store.upsert(ref)
        store.remove("webchat:u1")
        assert store.is_empty

    def test_remove_unknown_key(self, tmp_path: Path) -> None:
        store = ConversationReferenceStore(path=tmp_path / "refs.json")
        store.remove("nonexistent")

    def test_persistence(self, tmp_path: Path) -> None:
        path = tmp_path / "refs.json"
        store1 = ConversationReferenceStore(path=path)
        ref = ConversationReference(
            user=ChannelAccount(id="u1"),
            channel_id="test",
        )
        store1.upsert(ref)
        store2 = ConversationReferenceStore(path=path)
        assert store2.count == 1

    def test_corrupt_file(self, tmp_path: Path) -> None:
        path = tmp_path / "refs.json"
        path.write_text("not json")
        store = ConversationReferenceStore(path=path)
        assert store.is_empty

    def test_no_user_key(self, tmp_path: Path) -> None:
        store = ConversationReferenceStore(path=tmp_path / "refs.json")
        ref = ConversationReference(user=None, channel_id="webchat")
        store.upsert(ref)
        assert store.count == 1
