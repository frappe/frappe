import { describe, expect, it, vi } from "vitest";
import { loadPulseClient, fetchBootConfig } from "./pulse";

// The pulse client and its config load at runtime; each must degrade when unavailable.
vi.mock("../api", () => ({ runMethod: vi.fn().mockRejectedValue(new Error("offline")) }));

describe("telemetry plugin", () => {
  it("degrades to null when the client asset cannot be loaded", async () => {
    expect(await loadPulseClient()).toBeNull();
  });

  it("degrades to {} when the backend config is unreachable (e.g. old framework)", async () => {
    expect(await fetchBootConfig()).toEqual({});
  });
});
