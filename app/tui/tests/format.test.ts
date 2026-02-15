/**
 * Tests for formatting utilities.
 */

import { describe, test, expect } from "bun:test";
import { formatSize, formatSessionTime, formatDuration } from "../src/utils/format.js";

// -----------------------------------------------------------------------
// formatSize
// -----------------------------------------------------------------------

describe("formatSize", () => {
  test("returns bytes for values under 1 KB", () => {
    expect(formatSize(0)).toBe("0 B");
    expect(formatSize(512)).toBe("512 B");
    expect(formatSize(1023)).toBe("1023 B");
  });

  test("returns KB for values under 1 MB", () => {
    expect(formatSize(1024)).toBe("1.0 KB");
    expect(formatSize(1536)).toBe("1.5 KB");
    expect(formatSize(1024 * 1023)).toBe("1023.0 KB");
  });

  test("returns MB for values under 1 GB", () => {
    expect(formatSize(1024 * 1024)).toBe("1.0 MB");
    expect(formatSize(1024 * 1024 * 500)).toBe("500.0 MB");
  });

  test("returns GB for values >= 1 GB", () => {
    expect(formatSize(1024 * 1024 * 1024)).toBe("1.00 GB");
    expect(formatSize(1024 * 1024 * 1024 * 2.5)).toBe("2.50 GB");
  });
});

// -----------------------------------------------------------------------
// formatSessionTime
// -----------------------------------------------------------------------

describe("formatSessionTime", () => {
  test('returns "?" for undefined input', () => {
    expect(formatSessionTime(undefined)).toBe("?");
  });

  test('returns "?" for empty string', () => {
    expect(formatSessionTime("")).toBe("?");
  });

  test("formats a valid ISO timestamp", () => {
    const result = formatSessionTime("2024-06-15T14:30:00Z");
    // Should contain month abbreviation and time
    expect(result).toContain("Jun");
    expect(result).toContain("15");
  });

  test("handles invalid date gracefully", () => {
    const result = formatSessionTime("not-a-date");
    // Should try slice fallback
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });
});

// -----------------------------------------------------------------------
// formatDuration
// -----------------------------------------------------------------------

describe("formatDuration", () => {
  test("returns seconds for short durations", () => {
    expect(formatDuration(
      "2024-01-01T00:00:00Z",
      "2024-01-01T00:00:45Z",
    )).toBe("45s");
  });

  test("returns minutes and seconds", () => {
    expect(formatDuration(
      "2024-01-01T00:00:00Z",
      "2024-01-01T00:03:15Z",
    )).toBe("3m 15s");
  });

  test("returns hours and minutes", () => {
    expect(formatDuration(
      "2024-01-01T00:00:00Z",
      "2024-01-01T02:30:00Z",
    )).toBe("2h 30m");
  });

  test("returns empty string for negative duration", () => {
    expect(formatDuration(
      "2024-01-01T01:00:00Z",
      "2024-01-01T00:00:00Z",
    )).toBe("");
  });

  test("handles invalid dates by returning a string", () => {
    const result = formatDuration("bad", "worse");
    expect(typeof result).toBe("string");
  });

  test("returns 0s for identical timestamps", () => {
    expect(formatDuration(
      "2024-01-01T00:00:00Z",
      "2024-01-01T00:00:00Z",
    )).toBe("0s");
  });
});
