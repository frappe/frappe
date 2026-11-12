// What the bulk-run follower promises: it follows only runs a page asked for, keeps their progress
// across pages, reads the result from the Background Task once it settles, and toasts the counts.
import { beforeEach, describe, expect, it, vi } from "vitest";

const fake = vi.hoisted(() => ({
	getDocument: vi.fn(),
	toast: Object.assign(vi.fn(), {
		success: vi.fn(),
		warning: vi.fn(),
		error: vi.fn(),
	}),
}));

vi.mock("@framework/ui/api", () => ({ getDocument: fake.getDocument }));
vi.mock("frappe-ui", () => ({ toast: fake.toast }));

import {
	dismissBulkRun,
	followBulkRun,
	useBulkRuns,
	watchBulkRuns,
} from "../bulkRuns";

type Handler = (...args: unknown[]) => void;
const socket = {
	handlers: new Map<string, Handler[]>(),
	emit() {},
	on(event: string, handler: Handler) {
		socket.handlers.set(event, [
			...(socket.handlers.get(event) ?? []),
			handler,
		]);
	},
	off(event: string, handler: Handler) {
		socket.handlers.set(
			event,
			(socket.handlers.get(event) ?? []).filter((one) => one !== handler)
		);
	},
	fire(event: string, ...args: unknown[]) {
		for (const handler of socket.handlers.get(event) ?? []) handler(...args);
	},
};

const RESULT = {
	total: 3,
	done: ["a", "b"],
	failed: [{ name: "c", error: "Cannot delete c" }],
};

function row(fields: Record<string, unknown>) {
	return {
		data: {
			task_name: "Delete ToDo",
			status: "Queued",
			progress: 0,
			stage: "",
			...fields,
		},
	};
}

async function settle() {
	for (let turn = 0; turn < 5; turn++) await Promise.resolve();
}

let stop: () => void;

beforeEach(() => {
	stop?.();
	for (const run of useBulkRuns().value) dismissBulkRun(run.taskId);
	socket.handlers.clear();
	vi.clearAllMocks();
	fake.getDocument.mockResolvedValue(row({}));
	stop = watchBulkRuns(socket);
});

describe("following a run", () => {
	it("reads the Background Task once, for a run that moved before the page followed it", async () => {
		fake.getDocument.mockResolvedValue(
			row({ status: "Running", progress: 40, stage: "2 of 5" })
		);
		const run = followBulkRun("t1");
		await settle();

		expect(fake.getDocument).toHaveBeenCalledWith("Background Task", "t1");
		expect(run).toMatchObject({
			taskName: "Delete ToDo",
			status: "Running",
			progress: 40,
			stage: "2 of 5",
		});
	});

	it("keeps one run per task id however often it is followed", () => {
		const first = followBulkRun("t1");
		expect(followBulkRun("t1")).toBe(first);
		expect(useBulkRuns().value).toHaveLength(1);
		expect(fake.getDocument).toHaveBeenCalledTimes(1);
	});

	it("takes progress from task_update", async () => {
		const run = followBulkRun("t1");
		await settle();
		socket.fire("task_update", {
			task_id: "t1",
			task_name: "Delete ToDo",
			progress: 60,
			stage: "3 of 5",
		});
		socket.fire("task_update", { task_id: "t1", status: "Running" });

		expect(run).toMatchObject({
			status: "Running",
			progress: 60,
			stage: "3 of 5",
		});
	});

	it("ignores a task it was not asked to follow", async () => {
		socket.fire("task_update", { task_id: "other", status: "Completed" });
		await settle();

		expect(useBulkRuns().value).toEqual([]);
		expect(fake.getDocument).not.toHaveBeenCalled();
		expect(fake.toast.success).not.toHaveBeenCalled();
	});
});

describe("a run that settles", () => {
	it("reads the result and toasts done and failed counts, once", async () => {
		const settled = vi.fn();
		const run = followBulkRun("t1", settled);
		await settle();
		fake.getDocument.mockResolvedValue(
			row({
				status: "Completed",
				progress: 100,
				result: JSON.stringify(RESULT),
			})
		);
		socket.fire("task_update", {
			task_id: "t1",
			status: "Completed",
			progress: 100,
		});
		socket.fire("task_update", {
			task_id: "t1",
			status: "Completed",
			progress: 100,
		});
		await settle();

		expect(run.status).toBe("Completed");
		expect(run.result).toEqual(RESULT);
		expect(fake.toast.warning).toHaveBeenCalledTimes(1);
		expect(fake.toast.warning).toHaveBeenCalledWith(
			"Delete ToDo: 2 done, 1 failed"
		);
		expect(settled).toHaveBeenCalledTimes(1);
		expect(settled).toHaveBeenCalledWith(run);
	});

	it("toasts success when no record failed, and counts queued ones", async () => {
		fake.getDocument.mockResolvedValue(
			row({
				status: "Completed",
				result: JSON.stringify({
					total: 2,
					done: ["a"],
					failed: [],
					queued: ["b"],
				}),
			})
		);
		followBulkRun("t1");
		await settle();

		expect(fake.toast.success).toHaveBeenCalledWith(
			"Delete ToDo: 1 done, 0 failed, 1 queued"
		);
	});

	it("reads a run that had already finished when the page followed it", async () => {
		fake.getDocument.mockResolvedValue(
			row({
				status: "Completed",
				result: JSON.stringify({ total: 1, done: ["a"], failed: [] }),
			})
		);
		const settled = vi.fn();
		followBulkRun("t1", settled);
		await settle();

		expect(settled).toHaveBeenCalledTimes(1);
	});

	it("calls a listener added after the run settled at once", async () => {
		fake.getDocument.mockResolvedValue(
			row({
				status: "Completed",
				result: JSON.stringify({ total: 1, done: ["a"], failed: [] }),
			})
		);
		followBulkRun("t1");
		await settle();
		const late = vi.fn();
		followBulkRun("t1", late);

		expect(late).toHaveBeenCalledTimes(1);
	});

	it("shows a crashed run's last traceback line as its error", async () => {
		fake.getDocument.mockResolvedValue(
			row({
				status: "Failed",
				exception:
					"Traceback (most recent call last):\n  ...\nValueError: boom\n",
			})
		);
		const run = followBulkRun("t1");
		await settle();

		expect(run).toMatchObject({
			status: "Failed",
			result: null,
			error: "ValueError: boom",
		});
		expect(fake.toast.error).toHaveBeenCalledWith(
			"Delete ToDo: ValueError: boom"
		);
	});

	it("reports a result it cannot read instead of counting nothing", async () => {
		fake.getDocument.mockResolvedValue(
			row({ status: "Completed", result: "not json" })
		);
		const run = followBulkRun("t1");
		await settle();

		expect(run.result).toBeNull();
		expect(run.error).toBe("The result could not be read.");
		expect(fake.toast.error).toHaveBeenCalledTimes(1);
	});
});

describe("the tab's lifetime", () => {
	it("keeps the runs across pages: they live in the module, not in a component", async () => {
		const run = followBulkRun("t1");
		await settle();
		socket.fire("task_update", { task_id: "t1", progress: 20 });

		expect(useBulkRuns().value[0]).toBe(run);
		expect(useBulkRuns().value[0].progress).toBe(20);
	});

	it("rereads the runs still moving when the socket reconnects, not the settled ones", async () => {
		followBulkRun("moving");
		fake.getDocument.mockResolvedValue(
			row({
				status: "Completed",
				result: JSON.stringify({ total: 1, done: ["a"], failed: [] }),
			})
		);
		followBulkRun("done");
		await settle();
		fake.getDocument.mockClear();
		socket.fire("connect");
		await settle();

		expect(fake.getDocument.mock.calls.map((call) => call[1])).toEqual([
			"moving",
		]);
	});

	it("stops listening when stopped", async () => {
		const run = followBulkRun("t1");
		await settle();
		stop();
		socket.fire("task_update", { task_id: "t1", progress: 90 });

		expect(run.progress).toBe(0);
	});

	it("does nothing without a socket", () => {
		expect(() => watchBulkRuns(undefined)()).not.toThrow();
	});
});
