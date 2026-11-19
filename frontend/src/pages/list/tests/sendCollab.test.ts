import { beforeEach, describe, expect, it, vi } from "vitest";
import { sendCollab, type CollabCall } from "../collabCalls";

const fake = vi.hoisted(() => ({ bulk: vi.fn(), follow: vi.fn() }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@framework/ui/api")>()),
  bulkCollaborate: fake.bulk,
}));
vi.mock("@/shell/bulkRuns", () => ({ followBulkRun: fake.follow }));

const reload = vi.fn();
const selection = { names: ["A", "B"] };
const calls: CollabCall[] = [{ part: "assignments", method: "POST", bodies: [{ user: "x" }, { user: "y" }] }];

beforeEach(() => vi.clearAllMocks());

describe("sendCollab", () => {
  it("answers the calls of one kind as a single run, each failed name once", async () => {
    fake.bulk
      .mockResolvedValueOnce({ data: { total: 2, done: ["A"], failed: [{ name: "B", error: "no" }] } })
      .mockResolvedValueOnce({ data: { total: 2, done: ["A", "B"], failed: [{ name: "B", error: "again" }] } });
    const { data } = await sendCollab("ToDo", calls, selection, reload);
    expect(fake.bulk).toHaveBeenCalledTimes(2);
    expect(data).toEqual({ total: 2, done: ["A"], failed: [{ name: "B", error: "no" }] });
  });

  it("hands the shell the first background run and follows the rest itself", async () => {
    fake.bulk
      .mockResolvedValueOnce({ data: { task_id: "T1", job_id: "J1" } })
      .mockResolvedValueOnce({ data: { task_id: "T2", job_id: "J2" } });
    const { data } = await sendCollab("ToDo", calls, selection, reload);
    expect(data).toEqual({ task_id: "T1", job_id: "J1" });
    expect(fake.follow).toHaveBeenCalledTimes(1);
    expect(fake.follow).toHaveBeenCalledWith("T2", reload);
  });
});
