"""System prompt for the Realtime voice model."""

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

REALTIME_SYSTEM_PROMPT: str = (_TEMPLATES_DIR / "realtime_prompt.md").read_text()
