import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { requestMock } = vi.hoisted(() => ({ requestMock: vi.fn() }));

vi.mock("frappe-ui", () => ({ frappeRequest: requestMock }));

import { FLOW_ENABLED_METHOD, isFlowEnabled, resetFlowEnabled } from "../flow";

const flush = () => new Promise((resolve) => setTimeout(resolve));

describe("isFlowEnabled", () => {
  beforeEach(() => {
    resetFlowEnabled();
    requestMock.mockReset();
  });

  afterEach(() => {
    delete (globalThis as any).frappe;
  });

  it("reads Desk's boot without asking the server", () => {
    (globalThis as any).frappe = { boot: { flow_enabled: true } };

    expect(isFlowEnabled().value).toBe(true);
    expect(requestMock).not.toHaveBeenCalled();
  });

  it("asks the server once without a boot, and is null until it answers", async () => {
    requestMock.mockResolvedValue(true);

    const first = isFlowEnabled();
    const second = isFlowEnabled();
    expect(first.value).toBeNull();

    await flush();
    expect(first.value).toBe(true);
    expect(second.value).toBe(true);
    expect(requestMock).toHaveBeenCalledTimes(1);
    expect(requestMock).toHaveBeenCalledWith({ url: FLOW_ENABLED_METHOD, method: "GET" });
  });
});
