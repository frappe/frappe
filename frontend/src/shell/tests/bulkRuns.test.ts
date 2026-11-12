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
		fake.getDocument.mockResolvedValue(row({ status: "Running" }));
		const run = followBulkRun("t1");
		await settle();

		expect(fake.getDocument).toHaveBeenCalledWith("Background Task", "t1");
		expect(run).toMatchObject({
			taskName: "Delete ToDo",
			status: "Running",
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

	it("waits for the final row when a read sent earlier lands behind a newer event", async () => {
		vi.useFakeTimers();
		try {
			let land: (value: unknown) => void = () => {};
			fake.getDocument.mockReturnValueOnce(new Promise((resolve) => (land = resolve)));
			const run = followBulkRun("t1");
			fake.getDocument.mockResolvedValue(
				row({ status: "Completed", result: JSON.stringify({ total: 1, done: ["a"], failed: [] }) })
			);
			socket.fire("task_update", { task_id: "t1", status: "Completed" });
			land(row({ status: "Running" }));
			await vi.advanceTimersByTimeAsync(0);

			expect(run).toMatchObject({ status: "Completed", result: null });
			expect(fake.toast.error).not.toHaveBeenCalled();

			await vi.runAllTimersAsync();

			expect(run.result?.done).toEqual(["a"]);
			expect(fake.toast.success).toHaveBeenCalledTimes(1);
		} finally {
			vi.useRealTimers();
		}
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

	it("gives a reason when the owner cannot read the traceback", async () => {
		fake.getDocument.mockResolvedValue(row({ status: "Failed" }));
		const run = followBulkRun("t1");
		await settle();

		expect(run.error).toBe("The run stopped before it finished.");
	});

	it("retries a failed read three times, then settles a finished run with the error", async () => {
		vi.useFakeTimers();
		try {
			fake.getDocument.mockRejectedValue(new Error("502"));
			const run = followBulkRun("t1");
			socket.fire("task_update", { task_id: "t1", status: "Completed" });
			await vi.runAllTimersAsync();

			expect(fake.getDocument).toHaveBeenCalledTimes(3);
			expect(run).toMatchObject({ status: "Completed", result: null, error: "502" });
			expect(fake.toast.error).toHaveBeenCalledTimes(1);
		} finally {
			vi.useRealTimers();
		}
	});

	it("settles from the retry when the read recovers", async () => {
		vi.useFakeTimers();
		try {
			fake.getDocument.mockRejectedValueOnce(new Error("502"));
			fake.getDocument.mockResolvedValue(
				row({ status: "Completed", result: JSON.stringify({ total: 1, done: ["a"], failed: [] }) })
			);
			const run = followBulkRun("t1");
			socket.fire("task_update", { task_id: "t1", status: "Completed" });
			await vi.runAllTimersAsync();

			expect(run).toMatchObject({ status: "Completed", error: null });
			expect(run.result?.done).toEqual(["a"]);
			expect(fake.toast.success).toHaveBeenCalledTimes(1);
		} finally {
			vi.useRealTimers();
		}
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

	it("keeps the live progress when a reread lands after a reconnect", async () => {
		const run = followBulkRun("t1");
		await settle();
		socket.fire("task_update", { task_id: "t1", status: "Running", progress: 60, stage: "3 of 5" });
		fake.getDocument.mockResolvedValue(row({ status: "Running", progress: 0, stage: "" }));
		socket.fire("connect");
		await settle();

		expect(run).toMatchObject({ progress: 60, stage: "3 of 5" });
	});

	it("stops listening when stopped", async () => {
		const run = followBulkRun("t1");
		await settle();
		stop();
		socket.fire("task_update", { task_id: "t1", progress: 90 });
		fake.getDocument.mockClear();
		socket.fire("connect");

		expect(run.progress).toBe(0);
		expect(fake.getDocument).not.toHaveBeenCalled();
	});

	it("does nothing without a socket", () => {
		expect(() => watchBulkRuns(undefined)()).not.toThrow();
	});

	it("starts listening on the tab's socket with the first followed run", async () => {
		vi.resetModules();
		socket.handlers.clear();
		const { setBulkSocket } = await import("../bulkSocket");
		const fresh = await import("../bulkRuns");
		setBulkSocket(socket);

		expect(socket.handlers.size).toBe(0);
		const run = fresh.followBulkRun("t9");
		socket.fire("task_update", { task_id: "t9", progress: 40 });

		expect(run.progress).toBe(40);
		expect(socket.handlers.get("task_update")).toHaveLength(1);
	});

	it("keeps one listener however many runs are followed", () => {
		vi.resetModules();
		return Promise.all([import("../bulkSocket"), import("../bulkRuns")]).then(([{ setBulkSocket }, fresh]) => {
			socket.handlers.clear();
			setBulkSocket(socket);
			fresh.followBulkRun("a");
			fresh.followBulkRun("b");

			expect(socket.handlers.get("task_update")).toHaveLength(1);
			expect(socket.handlers.get("connect")).toHaveLength(1);
		});
	});
});

describe("a run that is not final", () => {
	it("retries a failed read, then waits for the next event", async () => {
		vi.useFakeTimers();
		try {
			fake.getDocument.mockRejectedValue(new Error("502"));
			const run = followBulkRun("t1");
			await vi.runAllTimersAsync();

			expect(fake.getDocument).toHaveBeenCalledTimes(3);
			expect(run).toMatchObject({ status: "Queued", error: null });
			expect(fake.toast.error).not.toHaveBeenCalled();
		} finally {
			vi.useRealTimers();
		}
	});

	it("stops announcing and listening once dismissed", async () => {
		const onSettled = vi.fn();
		const run = followBulkRun("t1", onSettled);
		dismissBulkRun("t1");
		socket.fire("task_update", { task_id: "t1", status: "Completed" });
		await settle();

		expect(run.status).toBe("Queued");
		expect(fake.toast.success).not.toHaveBeenCalled();
		expect(onSettled).not.toHaveBeenCalled();
	});

	it("settles on a Failed event whose row has no reason", async () => {
		fake.getDocument.mockResolvedValue(row({ status: "Failed" }));
		const onSettled = vi.fn();
		followBulkRun("t1", onSettled);
		socket.fire("task_update", { task_id: "t1", status: "Failed" });
		await settle();

		expect(onSettled).toHaveBeenCalledTimes(1);
	});

	it("runs the other listeners when one throws", async () => {
		const error = vi.spyOn(console, "error").mockImplementation(() => {});
		const later = vi.fn();
		fake.getDocument.mockResolvedValue(row({ status: "Failed" }));
		followBulkRun("t1", () => {
			throw new Error("bad listener");
		});
		followBulkRun("t1", later);
		await settle();

		expect(later).toHaveBeenCalledTimes(1);
		error.mockRestore();
	});
});
