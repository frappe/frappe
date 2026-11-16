import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { callMock } = vi.hoisted(() => ({ callMock: vi.fn() }));

vi.mock("frappe-ui", () => ({ call: callMock }));

import { FLOW_ENABLED_METHOD, isFlowEnabled, resetFlowEnabled } from "../flow";

const flush = () => new Promise((resolve) => setTimeout(resolve));

describe("isFlowEnabled", () => {
  beforeEach(() => {
    resetFlowEnabled();
    callMock.mockReset();
  });

  afterEach(() => {
    delete (globalThis as any).frappe;
  });

  it("reads Desk's boot without asking the server", () => {
    (globalThis as any).frappe = { boot: { flow_enabled: true } };

    expect(isFlowEnabled().value).toBe(true);
    expect(callMock).not.toHaveBeenCalled();
  });

  it("asks the server once without a boot, and is null until it answers", async () => {
    callMock.mockResolvedValue(true);

    const first = isFlowEnabled();
    const second = isFlowEnabled();
    expect(first.value).toBeNull();

    await flush();
    expect(first.value).toBe(true);
    expect(second.value).toBe(true);
    expect(callMock).toHaveBeenCalledTimes(1);
    expect(callMock).toHaveBeenCalledWith(FLOW_ENABLED_METHOD);
  });

  it("is false when the server can't answer", async () => {
    callMock.mockRejectedValue(new Error("404"));

    const enabled = isFlowEnabled();
    await flush();
    expect(enabled.value).toBe(false);
  });
});
