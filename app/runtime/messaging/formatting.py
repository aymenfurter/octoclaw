"""Markdown formatter for Telegram and plain-text fallback."""

from __future__ import annotations

import re


def markdown_to_telegram(text: str) -> str:
    """Convert standard Markdown to Telegram legacy Markdown."""
    placeholders: list[str] = []

    def _stash(m: re.Match) -> str:
        idx = len(placeholders)
        placeholders.append(m.group(0))
        return f"\x00PH{idx}\x00"

    text = re.sub(r"```(\w*)\n(.*?)```", _stash, text, flags=re.DOTALL)
    text = re.sub(r"`([^`\n]+)`", _stash, text)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)

    for idx, original in enumerate(placeholders):
        text = text.replace(f"\x00PH{idx}\x00", original, 1)

    return text.strip()


def strip_markdown(text: str) -> str:
    """Strip all Markdown formatting to produce clean plain text."""
    text = re.sub(r"```\w*\n(.*?)```", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)
    return text.strip()
