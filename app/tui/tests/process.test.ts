/**
 * Tests for the deploy/process helpers.
 */

import { describe, test, expect } from "bun:test";
import { stripAzWarnings } from "../src/deploy/process.js";

// -----------------------------------------------------------------------
// stripAzWarnings
// -----------------------------------------------------------------------

describe("stripAzWarnings", () => {
  test("passes clean text through unchanged", () => {
    const input = '{"name": "myapp"}';
    expect(stripAzWarnings(input)).toBe(input);
  });

  test("strips WARNING lines", () => {
    const input = [
      "WARNING: Some Azure CLI warning",
      "WARNING: Another warning line",
      '{"name": "myapp"}',
    ].join("\n");
    expect(stripAzWarnings(input)).toBe('{"name": "myapp"}');
  });

  test("strips behavior-altered lines", () => {
    const input = [
      "The behavior of this command has been altered by foo",
      '{"result": true}',
    ].join("\n");
    expect(stripAzWarnings(input)).toBe('{"result": true}');
  });

  test("handles mixed warnings and content", () => {
    const input = [
      '{"line1": 1}',
      "WARNING: something",
      '{"line2": 2}',
      "The behavior of this command has been altered by bar",
      '{"line3": 3}',
    ].join("\n");
    const expected = [
      '{"line1": 1}',
      '{"line2": 2}',
      '{"line3": 3}',
    ].join("\n");
    expect(stripAzWarnings(input)).toBe(expected);
  });

  test("handles empty string", () => {
    expect(stripAzWarnings("")).toBe("");
  });

  test("handles all-warning input", () => {
    const input = [
      "WARNING: A",
      "WARNING: B",
    ].join("\n");
    expect(stripAzWarnings(input)).toBe("");
  });

  test("trims whitespace from result", () => {
    const input = "\nWARNING: x\ndata\n  ";
    expect(stripAzWarnings(input)).toBe("data");
  });
});
