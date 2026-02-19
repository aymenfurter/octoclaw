/**
 * Mascot renderer -- the cat-in-crab-costume pixel art.
 *
 * The mascot is a 14x10 pixel grid rendered as 5 lines of half-block
 * art (▀▄█). Each pixel maps to a colour via MASCOT_PALETTE. Rendered
 * at runtime using TextNodeRenderable children (which support per-node
 * fg + bg) inside a TextRenderable per line.
 */

import { TextRenderable, TextNodeRenderable, type CliRenderer } from "@opentui/core";
import { MASCOT_GRID, MASCOT_PALETTE } from "../config/constants.js";

// -----------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------

interface MascotCell {
  char: string;
  fg?: string;
  bg?: string;
}

// -----------------------------------------------------------------------
// Build the half-block cells
// -----------------------------------------------------------------------

function buildMascotCells(): MascotCell[][] {
  const lines: MascotCell[][] = [];
  for (let row = 0; row < 10; row += 2) {
    const topRow = MASCOT_GRID[row];
    const botRow = MASCOT_GRID[row + 1];
    const cells: MascotCell[] = [];
    for (let col = 0; col < 14; col++) {
      const t = parseInt(topRow[col]);
      const b = parseInt(botRow[col]);
      const tc = MASCOT_PALETTE[t];
      const bc = MASCOT_PALETTE[b];
      if (!tc && !bc) {
        cells.push({ char: " " });
      } else if (!tc && bc) {
        cells.push({ char: "\u2584", fg: bc });          // ▄
      } else if (tc && !bc) {
        cells.push({ char: "\u2580", fg: tc });          // ▀
      } else if (t === b) {
        cells.push({ char: "\u2588", fg: tc });          // █
      } else {
        cells.push({ char: "\u2580", fg: tc, bg: bc });  // ▀ with bg
      }
    }
    lines.push(cells);
  }
  return lines;
}

/** Pre-computed mascot cells (5 rows of 14 half-block characters). */
export const MASCOT_CELLS = buildMascotCells();

/**
 * Create 5 TextRenderable lines that combine the mascot and the
 * POLYCLAW block text logo (one mascot line + logo text per row).
 *
 * Returns the array so the caller can add them to a header container.
 */
export function createMascotLogoLines(
  renderer: CliRenderer,
  logoText: readonly string[],
  logoColors: readonly string[],
): TextRenderable[] {
  const lines: TextRenderable[] = [];

  for (let i = 0; i < 5; i++) {
    const lineText = new TextRenderable(renderer, {
      id: `logo-${i}`,
      content: "",
      fg: logoColors[i],
    });

    // Mascot cells -- group consecutive cells with same fg+bg into segments
    const cells = MASCOT_CELLS[i];
    let seg = "";
    let segFg: string | undefined;
    let segBg: string | undefined;
    let segIdx = 0;

    const flush = () => {
      if (!seg) return;
      const node = new TextNodeRenderable({
        id: `m-${i}-${segIdx++}`,
        fg: segFg,
        bg: segBg,
      });
      node.children = [seg];
      lineText.add(node);
      seg = "";
    };

    for (const cell of cells) {
      if (cell.fg !== segFg || cell.bg !== segBg) {
        flush();
        segFg = cell.fg;
        segBg = cell.bg;
      }
      seg += cell.char;
    }
    flush();

    // Spacer + POLYCLAW text
    const logoNode = new TextNodeRenderable({
      id: `t-${i}`,
      fg: logoColors[i],
    });
    logoNode.children = [`  ${logoText[i]}`];
    lineText.add(logoNode);

    lines.push(lineText);
  }

  return lines;
}
