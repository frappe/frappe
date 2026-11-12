import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";
import type { ListMeta } from "@/list/defaults";
import { useBulkScope } from "@/list/useBulkScope";
import BulkStatusDialog from "../BulkStatusDialog.vue";
import { useBulkStatus, type BulkStatus, type BulkStatusAction } from "../bulkStatus";

const fake = vi.hoisted(() => ({
	actions: vi.fn(),
	run: vi.fn(),
	follow: vi.fn(),
	success: vi.fn(),
	info: vi.fn(),
}));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	bulkWorkflowActions: fake.actions,
	bulkStatusDocuments: fake.run,
}));
vi.mock("@/shell/bulkRuns", () => ({ followBulkRun: fake.follow }));
vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: fake.success, info: fake.info },
}));

let mounted: App | null = null;

async function settle() {
	for (let turn = 0; turn < 6; turn++) await nextTick();
	await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

const reload = vi.fn();

function status(
	meta: ListMeta | null,
	names = ["A", "B"],
	locked = false,
	{ total = names.length, approx = false } = {}
) {
	const selection = ref(names);
	const loaded = names.map((name) => ({ name }));
	const scope = useBulkScope({
		selection,
		rows: () => loaded as never,
		filters: () => ({ status: "Open" }),
		hasNextPage: () => total > names.length,
		totalCount: () => total,
		totalApprox: () => approx,
		exact: () => true,
	});
	let result!: BulkStatus;
	mounted = createApp(
		defineComponent({
			setup() {
				result = useBulkStatus({ doctype: "Leave", meta: ref(meta), selection, scope, cap: 500, locked, reload });
				return () => null;
			},
		})
	);
	mounted.mount(document.createElement("div"));
	return { status: result, selection, scope };
}

const named = (bulk: BulkStatus) => bulk.items.value.map(({ name, group, right }) => [name, group, right]);

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
	vi.useRealTimers();
	mounted?.unmount();
	mounted = null;
	document.body.innerHTML = "";
	vi.clearAllMocks();
});

describe("useBulkStatus", () => {
	it("offers Submit and Cancel in the danger group on a submittable doctype, each on its own right", () => {
		expect(named(status({ is_submittable: 1 }).status)).toEqual([
			["submit", "danger", "submit"],
			["cancel", "danger", "cancel"],
		]);
	});

	it("offers neither on a doctype that is not submittable or has a workflow", async () => {
		expect(status({}).status.items.value).toEqual([]);
		fake.actions.mockResolvedValue({ data: [] });
		expect(status({ is_submittable: 1, workflow_state_field: "workflow_state" }).status.items.value).toEqual([]);
		await vi.advanceTimersByTimeAsync(400);
	});

	it("reads the transitions common to the selection once it settles, and drops an older reply", async () => {
		fake.actions.mockImplementation(async (_doctype, selection) => ({
			data: selection.names.length === 2 ? ["Approve", "Reject"] : ["Approve"],
		}));
		const { status: bulk, selection } = status({ workflow_state_field: "workflow_state" });
		selection.value = ["A", "B", "C"];
		selection.value = ["A"];
		await vi.advanceTimersByTimeAsync(400);
		expect(fake.actions).toHaveBeenCalledTimes(1);
		expect(fake.actions).toHaveBeenCalledWith("Leave", { names: ["A"] });
		expect(named(bulk)).toEqual([["workflow-approve", "workflow", undefined]]);
	});

	it("drops the reply of an older selection that lands late", async () => {
		let late!: (reply: { data: string[] }) => void;
		fake.actions
			.mockReturnValueOnce(new Promise((resolve) => (late = resolve)))
			.mockResolvedValueOnce({ data: ["Reject"] });
		const { status: bulk, selection } = status({ workflow_state_field: "workflow_state" });
		await vi.advanceTimersByTimeAsync(400);
		selection.value = ["A"];
		await vi.advanceTimersByTimeAsync(400);
		late({ data: ["Approve"] });
		await vi.advanceTimersByTimeAsync(10);
		expect(named(bulk)).toEqual([["workflow-reject", "workflow", undefined]]);
	});

	it("reads nothing while the bar is locked", async () => {
		const { status: bulk } = status({ workflow_state_field: "workflow_state" }, ["A"], true);
		await vi.advanceTimersByTimeAsync(400);
		expect(fake.actions).not.toHaveBeenCalled();
		expect(bulk.items.value).toEqual([]);
	});

	it("keeps a workflow action that has no ASCII letters apart from another", async () => {
		fake.actions.mockResolvedValue({ data: ["承認", "却下"] });
		const { status: bulk } = status({ workflow_state_field: "workflow_state" });
		await vi.advanceTimersByTimeAsync(400);
		expect(bulk.items.value.map(({ name }) => name)).toEqual(["workflow-承認", "workflow-却下"]);
	});

	it("reloads the list and re-reads the actions when a run finishes", async () => {
		fake.actions.mockResolvedValue({ data: ["Hold"] });
		const { status: bulk } = status({ workflow_state_field: "workflow_state" });
		await vi.advanceTimersByTimeAsync(400);
		bulk.finished();
		await vi.advanceTimersByTimeAsync(400);
		expect(reload).toHaveBeenCalledTimes(1);
		expect(fake.actions).toHaveBeenCalledTimes(2);
	});

	it("reads the common actions again on refresh", async () => {
		fake.actions.mockResolvedValueOnce({ data: ["Hold"] }).mockResolvedValueOnce({ data: ["Escalate"] });
		const { status: bulk } = status({ workflow_state_field: "workflow_state" });
		await vi.advanceTimersByTimeAsync(400);
		expect(named(bulk)).toEqual([["workflow-hold", "workflow", undefined]]);
		bulk.refresh();
		await vi.advanceTimersByTimeAsync(400);
		expect(named(bulk)).toEqual([["workflow-escalate", "workflow", undefined]]);
	});

	it("asks with the selection frozen and names its scope", async () => {
		const { status: bulk, selection } = status({ is_submittable: 1 });
		(bulk.items.value[0].run as () => void)();
		selection.value = ["C"];
		expect(bulk.asked.value).toMatchObject({
			route: "bulk_submit",
			body: { names: ["A", "B"] },
			scope: "2 selected records",
		});
	});
});

describe("useBulkStatus over \"select all matching\"", () => {
	it("keeps Submit, Cancel and the workflow items, and owns their runs", async () => {
		fake.actions.mockResolvedValue({ data: ["Approve"] });
		const { status: bulk, scope } = status({ is_submittable: 1 }, ["A", "B"], false, { total: 1240 });
		scope.selectAll();
		await vi.advanceTimersByTimeAsync(400);
		expect(bulk.items.value.every((item) => bulk.owns(item.run))).toBe(true);
		expect(bulk.owns(() => {})).toBe(false);
	});

	it("asks over the filters and names the matching count", async () => {
		const { status: bulk, scope } = status({ is_submittable: 1 }, ["A", "B"], false, { total: 1240 });
		scope.selectAll();
		(bulk.items.value[0].run as () => void)();
		expect(bulk.asked.value).toMatchObject({
			route: "bulk_submit",
			body: { filters: { status: "Open" } },
			scope: "all 1,240 matching records",
		});
	});

	it("words a floor total with a plus and one match in the singular", () => {
		const floor = status({ is_submittable: 1 }, ["A"], false, { total: 10000, approx: true });
		floor.scope.selectAll();
		(floor.status.items.value[0].run as () => void)();
		expect(floor.status.asked.value?.scope).toBe("all 10,000+ matching records");

		const one = status({ is_submittable: 1 }, ["A"]);
		one.scope.selectAll();
		(one.status.items.value[0].run as () => void)();
		expect(one.status.asked.value?.scope).toBe("all 1 matching record");
	});

	it("reads the common transitions with the filters, and again when the filters stay but rows load", async () => {
		fake.actions.mockResolvedValue({ data: ["Approve", "Reject"] });
		const { status: bulk, scope, selection } = status(
			{ workflow_state_field: "workflow_state" },
			["A", "B"],
			false,
			{ total: 400 }
		);
		scope.selectAll();
		await vi.advanceTimersByTimeAsync(400);
		expect(fake.actions).toHaveBeenLastCalledWith("Leave", { filters: { status: "Open" } });
		expect(bulk.items.value.map(({ name }) => name)).toEqual(["workflow-approve", "workflow-reject"]);
		const reads = fake.actions.mock.calls.length;
		selection.value = ["A", "B"];
		await vi.advanceTimersByTimeAsync(400);
		expect(fake.actions).toHaveBeenCalledTimes(reads);
	});

	it("ends the scope when a run over it finishes", async () => {
		const { status: bulk, scope, selection } = status({ is_submittable: 1 }, ["A", "B"], false, { total: 1240 });
		scope.selectAll();
		bulk.finished();
		expect(scope.all.value).toBe(false);
		expect(selection.value).toEqual([]);
		expect(reload).toHaveBeenCalledTimes(1);
	});

	it("keeps a plain selection when a run finishes", () => {
		const { status: bulk, selection } = status({ is_submittable: 1 });
		bulk.finished();
		expect(selection.value).toEqual(["A", "B"]);
	});

	it("reads nothing over the cap", async () => {
		const { scope } = status({ workflow_state_field: "workflow_state" }, ["A", "B"], false, { total: 501 });
		scope.selectAll();
		fake.actions.mockClear();
		await vi.advanceTimersByTimeAsync(400);
		expect(fake.actions).not.toHaveBeenCalled();
	});
});

describe("BulkStatusDialog", () => {
	const action = (extra: Partial<BulkStatusAction> = {}): BulkStatusAction => ({
		route: "bulk_submit",
		label: "Submit",
		body: { names: ["A", "B"] },
		scope: "2 selected records",
		...extra,
	});

	async function open(asked: BulkStatusAction) {
		const host = document.createElement("div");
		document.body.append(host);
		const done = vi.fn();
		mounted = createApp({
			render: () => h(BulkStatusDialog, { modelValue: true, doctype: "Leave", action: asked, finished: done }),
		});
		mounted.mount(host);
		await vi.advanceTimersByTimeAsync(50);
		return done;
	}

	const text = () => document.body.textContent ?? "";
	async function confirm(label: string) {
		[...document.body.querySelectorAll("button")].find((one) => one.textContent?.trim() === label)!.click();
		await vi.advanceTimersByTimeAsync(50);
	}

	it("names the scope, then sends the selection to the action's route and reloads", async () => {
		fake.run.mockResolvedValue({ data: { total: 2, done: ["A", "B"], failed: [] } });
		const done = await open(action());
		expect(text()).toContain("Submit 2 selected records?");
		await confirm("Submit");
		expect(fake.run).toHaveBeenCalledWith("Leave", "bulk_submit", { names: ["A", "B"] });
		expect(fake.success).toHaveBeenCalledWith("2 records done");
		expect(done).toHaveBeenCalled();
	});

	it("names the matching scope and sends the filters", async () => {
		fake.run.mockResolvedValue({ data: { total: 1240, done: [], failed: [] } });
		const filters = { status: "Open" };
		await open(action({ body: { filters }, scope: "all 1,240 matching records" }));
		expect(text()).toContain("Submit all 1,240 matching records?");
		await confirm("Submit");
		expect(fake.run).toHaveBeenCalledWith("Leave", "bulk_submit", { filters });
	});

	it("sends a transition as the workflow action", async () => {
		fake.run.mockResolvedValue({ data: { total: 2, done: ["A", "B"], failed: [] } });
		await open(action({ route: "bulk_workflow", label: "Approve", transition: "Approve" }));
		await confirm("Approve");
		expect(fake.run).toHaveBeenCalledWith("Leave", "bulk_workflow", { names: ["A", "B"], action: "Approve" });
	});

	it("opens the result panel with the failures and the queued records", async () => {
		const { bulkPanel } = await import("@/shell/bulkOutcome");
		fake.run.mockResolvedValue({
			data: { total: 3, done: ["A"], queued: ["B"], failed: [{ name: "C", error: "Not saved" }] },
		});
		await open(action());
		await confirm("Submit");
		expect(bulkPanel.value).toMatchObject({
			label: "Submit",
			doctype: "Leave",
			total: 3,
			done: [{ name: "A" }],
			queued: [{ name: "B" }],
			failed: [{ name: "C", error: "Not saved" }],
		});
		bulkPanel.value = null;
	});

	it("toasts queued records when nothing failed", async () => {
		fake.run.mockResolvedValue({ data: { total: 2, done: [], queued: ["A", "B"], failed: [] } });
		await open(action());
		await confirm("Submit");
		expect(fake.info).toHaveBeenCalledWith("2 records queued");
	});

	it("hands a background run to the shell's follower", async () => {
		fake.run.mockResolvedValue({ data: { task_id: "T1", job_id: "J1" } });
		const done = await open(action());
		await confirm("Submit");
		expect(fake.follow).toHaveBeenCalledWith("T1", expect.any(Function));
		fake.follow.mock.calls[0][1]();
		expect(done).toHaveBeenCalled();
	});

	it("shows a refused run's message", async () => {
		fake.run.mockRejectedValue(new Error("Leave has a workflow: apply its actions instead."));
		await open(action());
		await confirm("Submit");
		expect(text()).toContain("apply its actions instead");
	});
});
