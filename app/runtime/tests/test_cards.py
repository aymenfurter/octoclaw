"""Tests for the CardQueue and card builders."""

from __future__ import annotations

from app.runtime.messaging.cards import (
    CardQueue,
    _adaptive_card_attachment,
    _build_card_actions,
    _hero_card_attachment,
    _thumbnail_card_attachment,
    _to_camel,
    attachment_to_dict,
)


class TestCardQueue:
    def test_enqueue_and_drain(self) -> None:
        q = CardQueue()
        att = _hero_card_attachment(title="Test")
        q.enqueue(att)
        cards = q.drain()
        assert len(cards) == 1
        assert q.drain() == []

    def test_drain_empty(self) -> None:
        q = CardQueue()
        assert q.drain() == []

    def test_thread_safety(self) -> None:
        import threading

        q = CardQueue()
        barrier = threading.Barrier(4)

        def writer() -> None:
            barrier.wait()
            for _ in range(50):
                q.enqueue(_hero_card_attachment(title="t"))

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        cards = q.drain()
        assert len(cards) == 200


class TestCardBuilders:
    def test_adaptive_card(self) -> None:
        att = _adaptive_card_attachment({"body": [{"type": "TextBlock", "text": "Hi"}]})
        assert att.content_type == "application/vnd.microsoft.card.adaptive"
        assert att.content["version"] == "1.5"

    def test_hero_card(self) -> None:
        att = _hero_card_attachment(title="T", subtitle="S", text="Body")
        assert att.content_type == "application/vnd.microsoft.card.hero"

    def test_thumbnail_card(self) -> None:
        att = _thumbnail_card_attachment(title="T")
        assert att.content_type == "application/vnd.microsoft.card.thumbnail"

    def test_hero_card_with_image(self) -> None:
        att = _hero_card_attachment(title="T", image_url="https://example.com/img.png")
        assert att.content.images is not None

    def test_build_card_actions_none(self) -> None:
        assert _build_card_actions(None) is None
        assert _build_card_actions([]) is None

    def test_build_card_actions(self) -> None:
        actions = _build_card_actions([{"title": "Go", "value": "https://example.com"}])
        assert actions is not None
        assert len(actions) == 1


class TestAttachmentSerialization:
    def test_attachment_to_dict(self) -> None:
        att = _adaptive_card_attachment({"body": []})
        d = attachment_to_dict(att)
        assert d["contentType"] == "application/vnd.microsoft.card.adaptive"
        assert isinstance(d["content"], dict)

    def test_hero_card_to_dict(self) -> None:
        att = _hero_card_attachment(title="T")
        d = attachment_to_dict(att)
        assert "content" in d


class TestCamelCase:
    def test_single_word(self) -> None:
        assert _to_camel("hello") == "hello"

    def test_multi_word(self) -> None:
        assert _to_camel("content_type") == "contentType"

    def test_three_words(self) -> None:
        assert _to_camel("my_long_name") == "myLongName"


class TestCardTools:
    """Test the raw card-building logic used by the tool functions."""

    def test_adaptive_card_queued(self) -> None:
        from app.runtime.messaging.cards import _default_queue
        _default_queue.drain()  # clear
        att = _adaptive_card_attachment({"body": []})
        _default_queue.enqueue(att)
        cards = _default_queue.drain()
        assert len(cards) == 1
        assert cards[0].content_type == "application/vnd.microsoft.card.adaptive"

    def test_hero_card_queued(self) -> None:
        from app.runtime.messaging.cards import _default_queue
        _default_queue.drain()
        att = _hero_card_attachment(title="Test", text="Body")
        _default_queue.enqueue(att)
        cards = _default_queue.drain()
        assert len(cards) == 1

    def test_carousel_multiple_types(self) -> None:
        from app.runtime.messaging.cards import _default_queue
        _default_queue.drain()
        _default_queue.enqueue(_hero_card_attachment(title="A"))
        _default_queue.enqueue(_thumbnail_card_attachment(title="B"))
        _default_queue.enqueue(_adaptive_card_attachment({"body": []}))
        cards = _default_queue.drain()
        assert len(cards) == 3
