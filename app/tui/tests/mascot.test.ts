/**
 * Tests for the mascot renderer -- half-block pixel art generation.
 *
 * We test the cell generation logic (pure function) rather than the
 * OpenTUI renderable integration which requires a live terminal.
 */

import { describe, test, expect } from "bun:test";
import { MASCOT_GRID, MASCOT_PALETTE } from "../src/config/constants.js";

// Replicate the pure-function logic from mascot.ts for testing
interface MascotCell {
  char: string;
  fg?: string;
  bg?: string;
}

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
        cells.push({ char: "\u2584", fg: bc }); // ▄
      } else if (tc && !bc) {
        cells.push({ char: "\u2580", fg: tc }); // ▀
      } else if (t === b) {
        cells.push({ char: "\u2588", fg: tc }); // █
      } else {
        cells.push({ char: "\u2580", fg: tc, bg: bc }); // ▀ with bg
      }
    }
    lines.push(cells);
  }
  return lines;
}

// -----------------------------------------------------------------------
// Tests
// -----------------------------------------------------------------------

describe("buildMascotCells", () => {
  const cells = buildMascotCells();

  test("produces 5 rows (10 pixel rows / 2)", () => {
    expect(cells).toHaveLength(5);
  });

  test("each row has 14 cells", () => {
    for (const row of cells) {
      expect(row).toHaveLength(14);
    }
  });

  test("every cell has exactly one character", () => {
    for (const row of cells) {
      for (const cell of row) {
        expect(cell.char).toHaveLength(1);
      }
    }
  });

  test("uses only valid half-block or space characters", () => {
    const validChars = new Set([" ", "\u2580", "\u2584", "\u2588"]);
    for (const row of cells) {
      for (const cell of row) {
        expect(validChars.has(cell.char)).toBe(true);
      }
    }
  });

  test("transparent pixels (0/0) produce a space with no color", () => {
    // Top-left corner is 0/0 in rows 0-1
    expect(cells[0][0]).toEqual({ char: " " });
  });

  test("colored pixels have valid hex fg colors", () => {
    for (const row of cells) {
      for (const cell of row) {
        if (cell.fg) {
          expect(cell.fg).toMatch(/^#[0-9A-Fa-f]{6}$/);
        }
        if (cell.bg) {
          expect(cell.bg).toMatch(/^#[0-9A-Fa-f]{6}$/);
        }
      }
    }
  });

  test("contains both shell red and face cream colors", () => {
    const allFg = new Set<string>();
    for (const row of cells) {
      for (const cell of row) {
        if (cell.fg) allFg.add(cell.fg);
      }
    }
    expect(allFg.has(MASCOT_PALETTE[1])).toBe(true); // shell red
    expect(allFg.has(MASCOT_PALETTE[3])).toBe(true); // face cream
  });
});
