/**
 * @vitest-environment jsdom
 */

import { describe, expect, it } from "vitest";
import { loadPulseClient, fetchBootConfig } from "./pulse";

// The queue / transport / capture logic lives in the canonical pulse client,
// loaded at runtime from pulse's CDN (version-independent of the frappe backend).
// frappe-ui's only job is to load it and its config and degrade gracefully when
// neither is available — which is exactly the case in the test environment, where
// the remote asset URL and the backend method can't be resolved.
describe("telemetry plugin", () => {
  it("degrades to null when the client asset cannot be loaded", async () => {
    expect(await loadPulseClient()).toBeNull();
  });

  it("degrades to {} when the backend config is unreachable (e.g. old framework)", async () => {
    expect(await fetchBootConfig()).toEqual({});
  });
});
