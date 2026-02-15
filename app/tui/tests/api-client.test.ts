/**
 * Tests for the API client.
 *
 * These tests verify request construction and response handling by
 * intercepting fetch. No real server is needed.
 */

import { describe, test, expect, beforeEach, afterEach } from "bun:test";
import { ApiClient } from "../src/api/client.js";

// -----------------------------------------------------------------------
// Mock setup
// -----------------------------------------------------------------------

const originalFetch = globalThis.fetch;
let fetchCalls: Array<[unknown, unknown]> = [];

function mockFetch(response: unknown, status = 200) {
  fetchCalls = [];
  globalThis.fetch = ((...args: unknown[]) => {
    fetchCalls.push([args[0], args[1]]);
    return Promise.resolve(
      new Response(JSON.stringify(response), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }) as typeof fetch;
}

// -----------------------------------------------------------------------
// Tests
// -----------------------------------------------------------------------

describe("ApiClient", () => {
  let api: ApiClient;

  beforeEach(() => {
    api = new ApiClient({
      baseUrl: "http://localhost:8080",
      adminSecret: "test-secret",
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("constructs correct web UI URL", () => {
    expect(api.webUiUrl).toBe("http://localhost:8080/?secret=test-secret");
  });

  test("webUiUrl omits secret param when empty", () => {
    const noSecret = new ApiClient({
      baseUrl: "http://localhost:8080",
      adminSecret: "",
    });
    expect(noSecret.webUiUrl).toBe("http://localhost:8080");
  });

  test("getSetupStatus sends GET to correct endpoint", async () => {
    const payload = {
      azure: { logged_in: true },
      copilot: { authenticated: true },
    };
    mockFetch(payload);

    const result = await api.getSetupStatus();
    expect(result).toEqual(payload);

    expect(fetchCalls).toHaveLength(1);
    const url = fetchCalls[0][0] as string;
    expect(url).toBe("http://localhost:8080/api/setup/status");
  });

  test("listSessions sends GET request", async () => {
    mockFetch([{ id: "s1", title: "Session 1" }]);
    const result = await api.listSessions();
    expect(result).toHaveLength(1);
    expect((result[0] as Record<string, unknown>).id).toBe("s1");
  });

  test("listModels fetches from /api/models", async () => {
    mockFetch({ models: [{ id: "gpt-4o", name: "GPT-4o" }] });
    const result = await api.listModels();
    expect(result).toHaveProperty("models");
  });

  test("azureLogin sends POST request", async () => {
    mockFetch({ status: "ok" });
    await api.azureLogin();

    expect(fetchCalls).toHaveLength(1);
    const opts = fetchCalls[0][1] as RequestInit;
    expect(opts.method).toBe("POST");

    const url = fetchCalls[0][0] as string;
    expect(url).toContain("/api/setup/azure/login");
  });

  test("throws on non-ok responses", async () => {
    mockFetch({ error: "not found" }, 404);
    await expect(api.getSetupStatus()).rejects.toThrow();
  });

  test("getSession fetches a specific session", async () => {
    mockFetch({ id: "s1", messages: [] });
    const result = await api.getSession("s1");
    expect(result).toHaveProperty("id");
  });

  test("listPlugins fetches plugins object", async () => {
    mockFetch({ plugins: [{ name: "github", enabled: true }] });
    const result = await api.listPlugins();
    expect(result).toHaveProperty("plugins");
  });
});
