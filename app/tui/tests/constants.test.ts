/**
 * Tests for application constants.
 */

import { describe, test, expect } from "bun:test";
import {
  LOGO_TEXT,
  LOGO_DIVIDER,
  MASCOT_GRID,
  MASCOT_PALETTE,
  SPINNER_FRAMES,
  STARTUP_PHASES,
  BAR_FILL,
  BAR_WIDTH,
  MAX_AC_VISIBLE,
  SLASH_COMMANDS,
  DISCLAIMER_FLAG,
  TAB_LABELS,
} from "../src/config/constants.js";

// -----------------------------------------------------------------------
// Logo
// -----------------------------------------------------------------------

describe("LOGO_TEXT", () => {
  test("has 5 rows of block text", () => {
    expect(LOGO_TEXT).toHaveLength(5);
  });

  test("all rows are strings", () => {
    for (const row of LOGO_TEXT) {
      expect(typeof row).toBe("string");
    }
  });
});

describe("LOGO_DIVIDER", () => {
  test("starts and ends with a diamond", () => {
    expect(LOGO_DIVIDER.trim().startsWith("◆")).toBe(true);
    expect(LOGO_DIVIDER.trim().endsWith("◆")).toBe(true);
  });
});

// -----------------------------------------------------------------------
// Mascot
// -----------------------------------------------------------------------

describe("MASCOT_GRID", () => {
  test("has 10 rows (for 5 half-block output lines)", () => {
    expect(MASCOT_GRID).toHaveLength(10);
  });

  test("each row is 14 characters wide", () => {
    for (const row of MASCOT_GRID) {
      expect(row).toHaveLength(14);
    }
  });

  test("only contains valid palette digits", () => {
    const validDigits = new Set(["0", "1", "3", "4", "5", "6", "7", "8"]);
    for (const row of MASCOT_GRID) {
      for (const ch of row) {
        expect(validDigits.has(ch)).toBe(true);
      }
    }
  });
});

describe("MASCOT_PALETTE", () => {
  test("defines colors for all non-zero MASCOT_GRID digits", () => {
    const digits = new Set<number>();
    for (const row of MASCOT_GRID) {
      for (const ch of row) {
        const n = parseInt(ch);
        if (n !== 0) digits.add(n);
      }
    }
    for (const d of digits) {
      expect(MASCOT_PALETTE[d]).toBeDefined();
      expect(MASCOT_PALETTE[d]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });
});

// -----------------------------------------------------------------------
// Spinner
// -----------------------------------------------------------------------

describe("SPINNER_FRAMES", () => {
  test("has 10 braille frames", () => {
    expect(SPINNER_FRAMES).toHaveLength(10);
  });
});

// -----------------------------------------------------------------------
// Startup phases
// -----------------------------------------------------------------------

describe("STARTUP_PHASES", () => {
  test("has a build phase first", () => {
    expect(STARTUP_PHASES[0].key).toBe("build");
  });

  test("each phase has key and label", () => {
    for (const phase of STARTUP_PHASES) {
      expect(typeof phase.key).toBe("string");
      expect(typeof phase.label).toBe("string");
    }
  });
});

// -----------------------------------------------------------------------
// Progress bar
// -----------------------------------------------------------------------

describe("Progress bar constants", () => {
  test("BAR_FILL is a full block character", () => {
    expect(BAR_FILL).toBe("\u2588");
  });

  test("BAR_WIDTH is positive", () => {
    expect(BAR_WIDTH).toBeGreaterThan(0);
  });
});

// -----------------------------------------------------------------------
// Slash commands
// -----------------------------------------------------------------------

describe("SLASH_COMMANDS", () => {
  test("has at least 20 commands", () => {
    expect(SLASH_COMMANDS.length).toBeGreaterThanOrEqual(20);
  });

  test("all commands start with /", () => {
    for (const sc of SLASH_COMMANDS) {
      expect(sc.cmd.startsWith("/")).toBe(true);
    }
  });

  test("all commands have a description", () => {
    for (const sc of SLASH_COMMANDS) {
      expect(sc.desc.length).toBeGreaterThan(0);
    }
  });

  test("no duplicate commands", () => {
    const cmds = SLASH_COMMANDS.map((s) => s.cmd);
    expect(new Set(cmds).size).toBe(cmds.length);
  });

  test("includes essential commands", () => {
    const cmds = new Set(SLASH_COMMANDS.map((s) => s.cmd));
    for (const essential of ["/new", "/model", "/status", "/help", "/quit"]) {
      expect(cmds.has(essential)).toBe(true);
    }
  });
});

// -----------------------------------------------------------------------
// Autocomplete
// -----------------------------------------------------------------------

describe("MAX_AC_VISIBLE", () => {
  test("is a positive integer", () => {
    expect(MAX_AC_VISIBLE).toBeGreaterThan(0);
    expect(Number.isInteger(MAX_AC_VISIBLE)).toBe(true);
  });
});

// -----------------------------------------------------------------------
// Disclaimer flag
// -----------------------------------------------------------------------

describe("DISCLAIMER_FLAG", () => {
  test("is a non-empty file path", () => {
    expect(DISCLAIMER_FLAG.length).toBeGreaterThan(0);
    expect(DISCLAIMER_FLAG).toContain("octoclaw_disclaimer");
  });
});

// -----------------------------------------------------------------------
// Tab labels
// -----------------------------------------------------------------------

describe("TAB_LABELS", () => {
  test("has labels matching the number of screens", () => {
    // 11 screens: Dashboard, Setup, Chat, Sessions, Skills, Plugins,
    //             MCP, Schedules, Proactive, Profile, Workspace
    expect(TAB_LABELS).toHaveLength(11);
  });

  test("first tab is Dashboard", () => {
    expect(TAB_LABELS[0]).toBe("Dashboard");
  });

  test("all labels are non-empty strings", () => {
    for (const label of TAB_LABELS) {
      expect(typeof label).toBe("string");
      expect(label.length).toBeGreaterThan(0);
    }
  });
});
