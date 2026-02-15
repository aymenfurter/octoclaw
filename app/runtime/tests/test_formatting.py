"""Tests for the formatting module."""

from __future__ import annotations

from app.runtime.messaging.formatting import markdown_to_telegram, strip_markdown


class TestMarkdownToTelegram:
    def test_bold(self) -> None:
        assert "*hello*" in markdown_to_telegram("**hello**")

    def test_headers(self) -> None:
        result = markdown_to_telegram("## Title")
        assert "*Title*" in result

    def test_code_block_preserved(self) -> None:
        src = "text\n```python\nprint('hi')\n```\nmore"
        result = markdown_to_telegram(src)
        assert "```python" in result

    def test_inline_code_preserved(self) -> None:
        result = markdown_to_telegram("use `foo` here")
        assert "`foo`" in result

    def test_strikethrough_removed(self) -> None:
        result = markdown_to_telegram("~~gone~~")
        assert "~~" not in result
        assert "gone" in result

    def test_horizontal_rule_removed(self) -> None:
        result = markdown_to_telegram("before\n---\nafter")
        assert "---" not in result

    def test_underline_converted(self) -> None:
        result = markdown_to_telegram("__underline__")
        assert "*underline*" in result

    def test_empty_string(self) -> None:
        assert markdown_to_telegram("") == ""


class TestStripMarkdown:
    def test_bold(self) -> None:
        assert strip_markdown("**hello**") == "hello"

    def test_headers(self) -> None:
        assert strip_markdown("### Title") == "Title"

    def test_code_block_content_kept(self) -> None:
        result = strip_markdown("```python\nprint('hi')\n```")
        assert "print('hi')" in result
        assert "```" not in result

    def test_links_expanded(self) -> None:
        result = strip_markdown("[click](http://example.com)")
        assert "click" in result
        assert "http://example.com" in result

    def test_strikethrough(self) -> None:
        assert strip_markdown("~~gone~~") == "gone"

    def test_italic_underscores(self) -> None:
        assert strip_markdown("_italic_") == "italic"

    def test_italic_asterisks(self) -> None:
        assert strip_markdown("*italic*") == "italic"

    def test_horizontal_rule(self) -> None:
        result = strip_markdown("before\n---\nafter")
        assert "---" not in result

    def test_plain_text_passthrough(self) -> None:
        assert strip_markdown("hello world") == "hello world"
