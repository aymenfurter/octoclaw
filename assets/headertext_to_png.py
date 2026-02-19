#!/usr/bin/env python3
"""
Render the POLYCLAW block-letter logo from the TUI (cli/src/ui.ts LOGO_TEXT)
pixel-for-pixel into a transparent PNG with the same gold gradient.

Each '\u2588' (full-block) in a row becomes a filled pixel; spaces become
transparent. Each of the 5 rows uses its corresponding gradient colour
from the TUI's LOGO_COLORS array.

The result is exported at a configurable scale (default 3x) for crisp
rendering in the web header.

Usage:
    python assets/headertext_to_png.py [--output app/frontend/public/headertext.png]
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit(
        "Pillow is required.  Install it with:\n"
        "  pip install Pillow"
    )

# ── Exact LOGO_TEXT from cli/src/ui.ts ──────────────────────────────────────
LOGO_TEXT = [
    " \u2588\u2588\u2588   \u2588\u2588\u2588\u2588  \u2588\u2588\u2588\u2588\u2588  \u2588\u2588\u2588   \u2588\u2588\u2588\u2588  \u2588      \u2588\u2588\u2588  \u2588   \u2588",
    "\u2588   \u2588 \u2588        \u2588   \u2588   \u2588 \u2588     \u2588     \u2588   \u2588 \u2588   \u2588",
    "\u2588   \u2588 \u2588        \u2588   \u2588   \u2588 \u2588     \u2588     \u2588\u2588\u2588\u2588\u2588 \u2588 \u2588 \u2588",
    "\u2588   \u2588 \u2588        \u2588   \u2588   \u2588 \u2588     \u2588     \u2588   \u2588 \u2588 \u2588 \u2588",
    " \u2588\u2588\u2588   \u2588\u2588\u2588\u2588    \u2588    \u2588\u2588\u2588   \u2588\u2588\u2588\u2588  \u2588\u2588\u2588\u2588\u2588 \u2588   \u2588  \u2588 \u2588 ",
]

# ── Gold gradient per row (from TUI LOGO_COLORS) ───────────────────────────
LOGO_COLORS = [
    "#FFD700",  # gold top
    "#E8C244",  # warm gold
    "#D4A843",  # tarnished gold
    "#B8860B",  # dark goldenrod
    "#DAA520",  # goldenrod base
]

PIXEL_SCALE = 3  # each character cell = 3x3 pixels


def _hex_to_rgba(h: str) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def render_headertext(output: str | Path, scale: int = PIXEL_SCALE) -> None:
    """Render the TUI block-letter logo as a transparent PNG."""
    rows = len(LOGO_TEXT)
    cols = max(len(line) for line in LOGO_TEXT)

    img_w = cols * scale
    img_h = rows * scale
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))

    for row_idx, line in enumerate(LOGO_TEXT):
        colour = _hex_to_rgba(LOGO_COLORS[row_idx])
        for col_idx, ch in enumerate(line):
            if ch == "\u2588":  # filled block
                for dy in range(scale):
                    for dx in range(scale):
                        img.putpixel((col_idx * scale + dx, row_idx * scale + dy), colour)

    # Crop to actual content
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    if bbox:
        img = img.crop(bbox)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output), format="PNG", optimize=True)

    print(f"Saved headertext ({img.size[0]}x{img.size[1]}, {scale}x scale) -> {output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render TUI POLYCLAW block-letter logo as a transparent PNG"
    )
    default_out = (
        Path(__file__).resolve().parent.parent
        / "app" / "frontend" / "public" / "headertext.png"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(default_out),
        help=f"Output file path (default: {default_out})",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=PIXEL_SCALE,
        help=f"Pixels per character cell (default: {PIXEL_SCALE})",
    )
    args = parser.parse_args()
    render_headertext(args.output, args.scale)


if __name__ == "__main__":
    main()
