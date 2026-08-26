// The reporter (wayfinder ticket 19 §3) as executable claims: it caps itself, and
// it never becomes the failure it is reporting.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { call } = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("frappe-ui", () => ({
  call,
  toast: { success: vi.fn(), error: vi.fn() },
}));

import {
  reportCustomizationError,
  resetCustomizationErrorReports,
  tierOf,
} from "../reportError";

function payload(index = 0) {
  return call.mock.calls[index][1];
}

describe("the customization error reporter", () => {
  beforeEach(() => {
    resetCustomizationErrorReports();
    call.mockReset();
    call.mockResolvedValue({});
  });

  it("reads the tier off the source, because attribution already carries it", () => {
    expect(tierOf("page-script:Refund Button")).toBe("page_script");
    expect(tierOf("host")).toBe("file_script");
    expect(tierOf("audit")).toBe("extension");
  });

  it("sends the error's message and stack apart", () => {
    const error = new Error("boom");
    error.stack = "at somewhere";
    reportCustomizationError(error, { source: "audit", event: "load" });

    expect(payload().message).toBe("boom");
    expect(payload().stack).toBe("at somewhere");
    expect(payload().tier).toBe("extension");
  });

  it("truncates before the request, not just at the server", () => {
    const error = new Error("m".repeat(5000));
    error.stack = "s".repeat(9000);
    reportCustomizationError(error, { source: "host", event: "onRefresh" });

    expect(payload().message).toHaveLength(1000);
    expect(payload().stack).toHaveLength(4000);
  });

  it("reports a source's event once per page session, killing the replay storm", () => {
    for (let attempt = 0; attempt < 5; attempt++)
      reportCustomizationError(new Error("boom"), {
        source: "page-script:A",
        event: "onRefresh",
      });

    expect(call).toHaveBeenCalledTimes(1);
  });

  it("still reports the same source's other events", () => {
    for (const event of ["onRefresh", "afterSave"])
      reportCustomizationError(new Error("boom"), {
        source: "page-script:A",
        event,
      });

    expect(call).toHaveBeenCalledTimes(2);
  });

  it("reports afresh once the session is reset", () => {
    const report = () =>
      reportCustomizationError(new Error("boom"), {
        source: "page-script:A",
        event: "onRefresh",
      });
    report();
    resetCustomizationErrorReports();
    report();

    expect(call).toHaveBeenCalledTimes(2);
  });

  it("swallows a rejected report rather than reporting the reporter", async () => {
    call.mockRejectedValue(new Error("network down"));

    expect(() =>
      reportCustomizationError(new Error("boom"), {
        source: "host",
        event: "load",
      }),
    ).not.toThrow();
    await Promise.resolve();
  });

  it("swallows a synchronous throw from call", () => {
    call.mockImplementation(() => {
      throw new Error("frappe-ui is not ready");
    });

    expect(() =>
      reportCustomizationError(new Error("boom"), {
        source: "host",
        event: "load",
      }),
    ).not.toThrow();
  });

  it("survives a call that hands back nothing at all", () => {
    call.mockReturnValue(undefined);

    expect(() =>
      reportCustomizationError(new Error("boom"), {
        source: "host",
        event: "load",
      }),
    ).not.toThrow();
  });

  it("takes an explicit tier, because the tier's own fetch has no script", () => {
    reportCustomizationError(new Error("boom"), {
      source: "page-scripts",
      tier: "page_script",
      event: "load",
      doctype: "CRM Deal",
    });

    expect(payload().tier).toBe("page_script");
    expect(payload().doctype).toBe("CRM Deal");
  });

  it("files one error once, at whichever site knew most about it", () => {
    // A tombstone hit reports itself, then throws into the handler catch, which
    // would otherwise file the same failure again under a duller name.
    const error = new Error("page.dialog.prompt was removed in 0.3.0");
    reportCustomizationError(error, {
      source: "page-script:A",
      event: "removed:dialog.prompt",
    });
    reportCustomizationError(error, {
      source: "page-script:A",
      event: "onRefresh",
    });

    expect(call).toHaveBeenCalledTimes(1);
  });
});
