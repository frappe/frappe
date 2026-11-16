import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { ActInvalid } from "@/acts/dispatcher";
import { assignUsers } from "../assignUsers";
import { useBulkCollaboration, type BulkTarget } from "../bulkCollaboration";

const fake = vi.hoisted(() => ({ bulk: vi.fn(), runBulk: vi.fn() }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	bulkCollaborate: fake.bulk,
}));
vi.mock("@/shell/bulkOutcome", () => ({ runBulk: fake.runBulk }));
vi.mock("@/shell/bulkRuns", () => ({ followBulkRun: vi.fn() }));
vi.mock("@framework/ui/useDoctypeMeta", () => ({ useDoctypeMeta: () => ({ meta: ref({}) }) }));

const after = { reload: vi.fn(), select: vi.fn() };
const target = (count = 2): BulkTarget => ({ selection: { names: ["A", "B"] }, count, all: false, approx: false });

// The shell's runBulk, minus its toasts: it calls `send` and the reply is the act's answer.
beforeEach(() => {
	vi.clearAllMocks();
	fake.runBulk.mockImplementation(({ send }) => send());
});

describe("assignUsers", () => {
	it("assigns every user to the selection with no dialog and answers the records done", async () => {
		fake.bulk.mockResolvedValue({ data: { total: 2, done: ["A", "B"], failed: [] } });
		const result = await assignUsers(["a@x", "b@x"], "ToDo", target(), after);
		expect(fake.bulk).toHaveBeenCalledTimes(2);
		expect(fake.bulk).toHaveBeenNthCalledWith(1, "ToDo", "assignments", "POST", { names: ["A", "B"] }, { user: "a@x" });
		expect(fake.bulk).toHaveBeenNthCalledWith(2, "ToDo", "assignments", "POST", { names: ["A", "B"] }, { user: "b@x" });
		expect(result).toEqual({ assigned: ["A", "B"], failed: [], background: false });
		expect(fake.runBulk).toHaveBeenCalledWith(expect.objectContaining({ doctype: "ToDo", finished: after.reload, select: after.select }));
	});

	it("lists the records the server refused and leaves them out of assigned", async () => {
		fake.bulk.mockResolvedValue({ data: { total: 2, done: ["A", "B"], failed: [{ name: "B", error: "no" }] } });
		const result = await assignUsers(["a@x"], "ToDo", target(), after);
		expect(result).toEqual({ assigned: ["A"], failed: [{ name: "B", error: "no" }], background: false });
	});

	it("sends a user named twice once", async () => {
		fake.bulk.mockResolvedValue({ data: { total: 2, done: ["A", "B"], failed: [] } });
		await assignUsers(["a@x", "a@x"], "ToDo", target(), after);
		expect(fake.bulk).toHaveBeenCalledTimes(1);
	});

	it("says a background run is not done yet", async () => {
		fake.bulk.mockResolvedValue({ data: { task_id: "T1", job_id: "J1" } });
		expect(await assignUsers(["a@x"], "ToDo", target(), after)).toEqual({ assigned: [], failed: [], background: true });
	});

	it("refuses with no rows selected or no users, and sends nothing", async () => {
		await expect(assignUsers(["a@x"], "ToDo", target(0), after)).rejects.toThrow(ActInvalid);
		await expect(assignUsers([], "ToDo", target(), after)).rejects.toThrow(/list of user ids/);
		expect(fake.bulk).not.toHaveBeenCalled();
	});
});

describe("the assign item", () => {
	const assign = (collab = useBulkCollaboration("ToDo", target, "jane@example.com", after)) =>
		collab.items().find((item) => item.name === "assign")!;

	it("takes the caller's users, and opens the dialog when given none", async () => {
		fake.bulk.mockResolvedValue({ data: { total: 2, done: ["A", "B"], failed: [] } });
		const collab = useBulkCollaboration("ToDo", target, "jane@example.com", after);
		const item = assign(collab);
		expect(item.values).toBe(true);
		expect(await item.run!({} as never, ["a@x"])).toMatchObject({ assigned: ["A", "B"] });
		expect(collab.request.value).toBeNull();
		await item.run!({} as never);
		expect(collab.request.value).toMatchObject({ kind: "assign", count: 2 });
	});

	it("is the only collaboration item that takes the caller's value", () => {
		const others = useBulkCollaboration("ToDo", target, "jane@example.com", after)
			.items()
			.filter((item) => item.name !== "assign");
		expect(others.some((item) => item.values)).toBe(false);
	});
});
