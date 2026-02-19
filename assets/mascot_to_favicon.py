#!/usr/bin/env python3
"""
Convert the polyclaw CLI mascot pixel grid (from cli/src/ui.ts)
into a favicon (.ico) with standard multi-resolution layers and transparency.

Generates an ICO file containing 16x16, 32x32, and 48x48 layers,
all derived from the 14x10 mascot grid centered on a square canvas.

Usage:
    python assets/mascot_to_favicon.py [--output assets/favicon.ico]
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

# ── Pixel grid (14 wide x 10 tall) ─────────────────────────────────────────
# 0 = transparent, other digits map to PALETTE colours.
MASCOT_GRID = [
    "00060000060000",  # antennae tips
    "00006000060000",  # antennae stems
    "00011111111000",  # shell top
    "00151111115100",  # shell + inner ears
    "01113333331110",  # shell sides + face
    "01134433443110",  # eyes
    "01183333338110",  # cheeks (blush)
    "00133388333100",  # tongue / mouth
    "00013333331000",  # chin
    "00001111110000",  # shell bottom
]

# ── Colour palette (hex → RGBA) ────────────────────────────────────────────
PALETTE: dict[int, tuple[int, int, int, int]] = {
    0: (0, 0, 0, 0),            # transparent
    1: (0xD0, 0x30, 0x30, 255), # shell (red)
    3: (0xF5, 0xE6, 0xD2, 255), # face (cream)
    4: (0x1E, 0x14, 0x14, 255), # eyes (near-black)
    5: (0xFF, 0xA0, 0xA0, 255), # inner ear (pink)
    6: (0xFF, 0x6B, 0x20, 255), # antenna (orange)
    7: (0x78, 0x37, 0x37, 255), # mouth (dark red)
    8: (0xFF, 0x82, 0x96, 255), # accent/blush (pink)
}

GRID_W = len(MASCOT_GRID[0])  # 14
GRID_H = len(MASCOT_GRID)     # 10


def _raw_image() -> Image.Image:
    """Create a 1x-scale RGBA image of the mascot on a square canvas."""
    # Square canvas sized to the larger dimension so the mascot is centred.
    side = max(GRID_W, GRID_H)  # 14
    img = Image.new("RGBA", (side, side), (0, 0, 0, 0))

    y_offset = (side - GRID_H) // 2  # vertical centering
    x_offset = (side - GRID_W) // 2  # horizontal centering (0 here)

    for y, row in enumerate(MASCOT_GRID):
        for x, ch in enumerate(row):
            colour = PALETTE[int(ch)]
            if colour[3] == 0:
                continue
            img.putpixel((x_offset + x, y_offset + y), colour)

    return img


def render_favicon(output: str | Path) -> None:
    """Render a multi-resolution .ico file optimised for favicons."""
    raw = _raw_image()  # 14x14 square, centred

    # Standard favicon sizes
    sizes = [16, 32, 48]
    layers: list[Image.Image] = []

    for size in sizes:
        # NEAREST keeps pixel-art crisp at small sizes
        layer = raw.resize((size, size), Image.Resampling.NEAREST)
        layers.append(layer)

    # Save as ICO with all layers
    layers[0].save(
        str(output),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=layers[1:],
    )

    size_str = ", ".join(f"{s}x{s}" for s in sizes)
    print(f"Saved favicon ({size_str}) → {output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render polyclaw mascot as a multi-resolution favicon"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path(__file__).resolve().parent / "favicon.ico"),
        help="Output file path (default: assets/favicon.ico)",
    )
    args = parser.parse_args()
    render_favicon(args.output)


if __name__ == "__main__":
    main()
