import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import BulkCollabDialog from "../BulkCollabDialog.vue";
import type { CollabRequest } from "../bulkCollaboration";

const fake = vi.hoisted(() => ({
  bulk: vi.fn(),
  run: vi.fn(),
}));

vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@framework/ui/api")>()),
  bulkCollaborate: fake.bulk,
}));
vi.mock("@/shell/bulkOutcome", () => ({ runBulk: fake.run }));

let mounted: App | null = null;
const reload = vi.fn();
const select = vi.fn();

// The shell's runBulk reports the reply; here it only sends, as a refusal must reach the dialog.
beforeEach(() => {
  fake.run.mockImplementation(async ({ send }) => void (await send()));
});

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
    render: () => h(BulkCollabDialog, { request, doctype: "ToDo", reload, select }),
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
    expect(fake.run).toHaveBeenCalledWith(
      expect.objectContaining({ label: "Clear assignment", doctype: "ToDo", select, finished: reload }),
    );
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

  it("retries the failed names alone", async () => {
    fake.bulk.mockResolvedValue({ data: { total: 1, done: ["B"], failed: [] } });
    fake.run.mockImplementation(async ({ send }) => void (await send(["B"])));
    await open("mark_seen");
    await press("Mark as seen");
    expect(fake.bulk).toHaveBeenCalledWith("ToDo", "seen", "POST", { names: ["B"] }, {});
  });

  it("closes once the shell reports the run", async () => {
    fake.bulk.mockResolvedValue({ data: { task_id: "T1", job_id: "J1" } });
    await open("mark_seen");
    await press("Mark as seen");
    expect(fake.bulk).toHaveBeenCalledTimes(1);
    expect(text()).not.toContain("Mark as seen");
  });

  it("shows why the whole run was refused", async () => {
    fake.bulk.mockRejectedValue(
      new Error("No enabled assignment rule for ToDo"),
    );
    await open("apply_assignment_rule");
    await press("Apply assignment rule");
    expect(text()).toContain("No enabled assignment rule for ToDo");
  });
});
