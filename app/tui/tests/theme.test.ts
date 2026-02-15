/**
 * Tests for the color theme constants.
 */

import { describe, test, expect } from "bun:test";
import { Colors, LogoColors, ShadowColor, GradientColors } from "../src/utils/theme.js";

describe("Colors palette", () => {
  test("has all required color keys", () => {
    const requiredKeys = [
      "bg", "surface", "border", "accent", "green",
      "red", "yellow", "purple", "text", "muted", "dim",
    ];
    for (const key of requiredKeys) {
      expect(Colors).toHaveProperty(key);
    }
  });

  test("all values are valid hex color strings", () => {
    for (const value of Object.values(Colors)) {
      expect(value).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });
});

describe("LogoColors", () => {
  test("has exactly 5 gold-range colors", () => {
    expect(LogoColors).toHaveLength(5);
    for (const c of LogoColors) {
      expect(c).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });
});

describe("ShadowColor", () => {
  test("is a valid hex color", () => {
    expect(ShadowColor).toMatch(/^#[0-9A-Fa-f]{6}$/);
  });
});

describe("GradientColors", () => {
  test("has 30 entries for smooth animation", () => {
    expect(GradientColors).toHaveLength(30);
  });

  test("all entries are valid hex colors", () => {
    for (const c of GradientColors) {
      expect(c).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  test("starts and ends with dark gold tones", () => {
    // The gradient ramps from dark gold -> bright -> back to dark gold
    expect(GradientColors[0]).toMatch(/^#[89A]/);
    expect(GradientColors[GradientColors.length - 1]).toMatch(/^#[89A]/);
  });
});
