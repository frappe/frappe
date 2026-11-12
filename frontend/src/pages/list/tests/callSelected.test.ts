// page.callSelected: the request the runner takes, and what the person sees when it answers.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { bulkCallDocuments, followBulkRun, toast } = vi.hoisted(() => ({
  bulkCallDocuments: vi.fn(),
  followBulkRun: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock("@framework/ui/api", () => ({
  bulkCallDocuments,
  isBulkQueued: (result: object) => "task_id" in result,
}));
vi.mock("@/shell/bulkRuns", () => ({ followBulkRun }));
vi.mock("frappe-ui", () => ({ toast }));

import { callSelected } from "../callSelected";

const reload = vi.fn();
const host = (selected: object = { names: ["a@example.com", "b@example.com"] }) => ({
  doctype: "User",
  selected: () => selected,
  reload,
});

beforeEach(() => vi.clearAllMocks());

describe("callSelected", () => {
  it("sends the method, its args and the selection to the runner", async () => {
    bulkCallDocuments.mockResolvedValue({ data: { total: 2, done: ["a@example.com", "b@example.com"], failed: [] } });
    const ok = await callSelected(host(), "my_app.api.add_roles", { roles: ["Blogger"] });

    expect(bulkCallDocuments).toHaveBeenCalledWith("User", {
      names: ["a@example.com", "b@example.com"],
      method: "my_app.api.add_roles",
      args: { roles: ["Blogger"] },
    });
    expect(ok).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(toast.success).toHaveBeenCalledTimes(1);
  });

  it("sends the filter when the selection is a filter", async () => {
    bulkCallDocuments.mockResolvedValue({ data: { total: 1, done: ["a"], failed: [] } });
    await callSelected(host({ filters: [["enabled", "=", 1]] }), "my_app.api.add_roles");

    expect(bulkCallDocuments).toHaveBeenCalledWith("User", {
      filters: [["enabled", "=", 1]],
      method: "my_app.api.add_roles",
      args: undefined,
    });
  });

  it("follows a background run and reloads when it settles", async () => {
    bulkCallDocuments.mockResolvedValue({ data: { task_id: "T-1", job_id: "T-1" } });
    const ok = await callSelected(host(), "my_app.api.add_roles");

    expect(ok).toBe(true);
    expect(followBulkRun).toHaveBeenCalledWith("T-1", reload);
    expect(reload).not.toHaveBeenCalled();
    expect(toast.info).toHaveBeenCalledTimes(1);
  });

  it("says how many records the method queued elsewhere", async () => {
    bulkCallDocuments.mockResolvedValue({ data: { total: 2, done: [], failed: [], queued: ["a", "b"] } });

    expect(await callSelected(host(), "my_app.api.add_roles")).toBe(true);
    expect(toast.info.mock.calls[0][0]).toBe("2 records queued");
  });

  it("resolves false and names the first failure when a record fails", async () => {
    bulkCallDocuments.mockResolvedValue({
      data: { total: 2, done: ["a"], failed: [{ name: "b", error: "Not permitted" }] },
    });

    expect(await callSelected(host(), "my_app.api.add_roles")).toBe(false);
    expect(toast.error.mock.calls[0][0]).toContain("b: Not permitted");
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("resolves false with the server's message when the runner refuses", async () => {
    bulkCallDocuments.mockRejectedValue(new Error("You are not allowed to run bulk actions."));

    expect(await callSelected(host(), "my_app.api.add_roles")).toBe(false);
    expect(toast.error).toHaveBeenCalledWith("You are not allowed to run bulk actions.");
    expect(reload).not.toHaveBeenCalled();
  });

  it("sends nothing while no row is selected", async () => {
    expect(await callSelected(host({ names: [] }), "my_app.api.add_roles")).toBe(false);
    expect(bulkCallDocuments).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledTimes(1);
  });
});
