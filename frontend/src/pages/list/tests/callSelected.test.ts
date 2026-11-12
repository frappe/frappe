// page.callSelected: the request the runner takes, and who reports the outcome.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { bulkCallDocuments, runBulk, toast } = vi.hoisted(() => ({
  bulkCallDocuments: vi.fn(),
  runBulk: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock("@framework/ui/api", () => ({ bulkCallDocuments }));
vi.mock("@/shell/bulkOutcome", () => ({ runBulk }));
vi.mock("frappe-ui", () => ({ toast }));

import { callSelected } from "../callSelected";

const reload = vi.fn();
const host = (selected: object = { names: ["a@example.com", "b@example.com"] }) => ({
  doctype: "User",
  selected: () => selected,
  reload,
});

beforeEach(() => {
  vi.clearAllMocks();
  runBulk.mockImplementation(async (options) => {
    await options.send();
  });
});

describe("callSelected", () => {
  it("hands the runner a labelled act that sends the method, its args and the selection", async () => {
    const ok = await callSelected(host(), "my_app.api.add_roles", { roles: ["Blogger"] });

    expect(ok).toBe(true);
    expect(runBulk.mock.calls[0][0]).toMatchObject({ label: "Add Roles", doctype: "User", finished: reload });
    expect(bulkCallDocuments).toHaveBeenCalledWith("User", {
      names: ["a@example.com", "b@example.com"],
      method: "my_app.api.add_roles",
      args: { roles: ["Blogger"] },
    });
  });

  it("sends the filter when the selection is a filter", async () => {
    await callSelected(host({ filters: { status: "Open" } }), "my_app.api.close");

    expect(bulkCallDocuments).toHaveBeenCalledWith("User", {
      filters: { status: "Open" },
      method: "my_app.api.close",
      args: undefined,
    });
  });

  it("sends only the failed names on a retry", async () => {
    runBulk.mockImplementation(async (options) => {
      await options.send(["b@example.com"]);
    });
    await callSelected(host(), "my_app.api.add_roles");

    expect(bulkCallDocuments.mock.calls[0][1].names).toEqual(["b@example.com"]);
  });

  it("resolves false with the server's message when the runner refuses", async () => {
    runBulk.mockRejectedValue(new Error("Too many records"));

    expect(await callSelected(host(), "my_app.api.add_roles")).toBe(false);
    expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("Too many records"));
  });

  it("sends nothing while no row is selected", async () => {
    expect(await callSelected(host({ names: [] }), "my_app.api.add_roles")).toBe(false);
    expect(runBulk).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledTimes(1);
  });
});
