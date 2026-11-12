import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import BulkCollabDialog from "../BulkCollabDialog.vue";
import type { CollabRequest } from "../bulkCollaboration";

const fake = vi.hoisted(() => ({
  bulk: vi.fn(),
  follow: vi.fn(),
  success: vi.fn(),
  info: vi.fn(),
}));

vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@framework/ui/api")>()),
  bulkCollaborate: fake.bulk,
}));
vi.mock("@/shell/bulkRuns", () => ({ followBulkRun: fake.follow }));
vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("frappe-ui")>()),
  toast: { success: fake.success, info: fake.info },
}));

let mounted: App | null = null;
const reload = vi.fn();

async function settle() {
  for (let turn = 0; turn < 6; turn++) await nextTick();
  await new Promise((resolve) => setTimeout(resolve));
  await nextTick();
}

async function open(kind: CollabRequest["kind"], all = false) {
  const request = {
    kind,
    selection: all ? { filters: { status: "Open" } } : { names: ["A", "B"] },
    count: 2,
    all,
    approx: false,
  };
  const host = document.createElement("div");
  document.body.append(host);
  mounted = createApp({
    render: () => h(BulkCollabDialog, { request, doctype: "ToDo", reload }),
  });
  mounted.mount(host);
  await settle();
}

async function press(label: string) {
  const button = Array.from(document.body.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === label,
  );
  button!.click();
  await settle();
}

const text = () => document.body.textContent ?? "";

afterEach(() => {
  mounted?.unmount();
  mounted = null;
  document.body.innerHTML = "";
  vi.clearAllMocks();
});

describe("BulkCollabDialog", () => {
  it("names the scope, and sends the selection to the part's route", async () => {
    fake.bulk.mockResolvedValue({
      data: { total: 2, done: ["A", "B"], failed: [] },
    });
    await open("clear_assignment");
    expect(text()).toContain(
      "This cancels every assignment on 2 selected records.",
    );
    await press("Clear assignment");
    expect(fake.bulk).toHaveBeenCalledWith(
      "ToDo",
      "assignments",
      "DELETE",
      { names: ["A", "B"] },
      {},
    );
    expect(fake.success).toHaveBeenCalledWith("Done on 2 records");
    expect(reload).toHaveBeenCalled();
  });

  it("sends the filters when all the matching records are chosen", async () => {
    fake.bulk.mockResolvedValue({
      data: { total: 2, done: ["A"], failed: [] },
    });
    await open("follow", true);
    await press("Follow");
    expect(fake.bulk).toHaveBeenCalledWith(
      "ToDo",
      "follows",
      "POST",
      { filters: { status: "Open" } },
      {},
    );
  });

  it("follows a queued run in the background", async () => {
    fake.bulk.mockResolvedValue({ data: { task_id: "T1", job_id: "J1" } });
    await open("mark_seen");
    await press("Mark as seen");
    expect(fake.follow).toHaveBeenCalledWith("T1", reload);
    expect(fake.info).toHaveBeenCalledWith("Running in the background");
  });

  it("keeps the dialog open with each failure, one per line", async () => {
    fake.bulk.mockResolvedValue({
      data: {
        total: 2,
        done: ["A"],
        failed: [{ name: "B", error: "No rule" }],
      },
    });
    await open("apply_assignment_rule");
    await press("Apply assignment rule");
    expect(text()).toContain("B: No rule");
    expect(text()).toContain("Close");
  });

  it("shows why the whole run was refused", async () => {
    fake.bulk.mockRejectedValue(
      new Error("No enabled assignment rule for ToDo"),
    );
    await open("apply_assignment_rule");
    await press("Apply assignment rule");
    expect(text()).toContain("No enabled assignment rule for ToDo");
    expect(fake.success).not.toHaveBeenCalled();
  });
});
