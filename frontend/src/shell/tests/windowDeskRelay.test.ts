// The tab's end of the UI relay: one call at a time through `window.desk`, a parked confirm answered later.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runMethod = vi.fn(async (..._args: unknown[]) => ({ data: null }));
vi.mock("@framework/ui/api", () => ({ runMethod: (...args: unknown[]) => runMethod(...args) }));

import { startRelay } from "../windowDesk/relay";
import { claimTabId } from "../windowDesk/tabId";

type Handler = (event: unknown) => void;

function socket() {
	const handlers: Handler[] = [];
	return { on: (_name: string, handler: Handler) => handlers.push(handler), off: vi.fn(), emit: (event: unknown) => handlers.forEach((handler) => handler(event)) };
}

const result = (data: unknown) => ({ ok: true, data, route: "/apps/x", dialogs: [] });
const replies = () => runMethod.mock.calls.map(([, body]) => body as any);
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

async function started(desk: Record<string, unknown>) {
	Object.defineProperty(window, "desk", { value: desk, configurable: true, writable: true });
	const relay = socket();
	await startRelay(relay as any);
	return relay;
}

beforeEach(() => {
	sessionStorage.clear();
	sessionStorage.setItem("desk-tab", "tab1");
	runMethod.mockClear();
	// Node's channels reach every instance in the process, so a finished test's tab would answer the next one's claim.
	vi.stubGlobal("BroadcastChannel", undefined);
});
afterEach(() => {
	delete (window as any).desk;
	vi.unstubAllGlobals();
});

describe("the relay in the tab", () => {
	it("names itself to a hello with its route, title and focus time", async () => {
		const relay = await started({});
		relay.emit({ call_id: "hello1", op: "tabs" });

		const [reply] = replies();
		expect(reply.call_id).toBe("hello1");
		expect(reply.result).toMatchObject({ tab: "tab1", route: expect.any(String), title: expect.any(String) });
		expect(typeof reply.result.focused_at).toBe("number");
	});

	it("ignores a call for another tab", async () => {
		const run = vi.fn();
		const relay = await started({ acts: { run } });
		relay.emit({ call_id: "c1", op: "run", tab: "other", act: "go" });
		await settle();

		expect(run).not.toHaveBeenCalled();
		expect(runMethod).not.toHaveBeenCalled();
	});

	it("runs an act and posts its result as final", async () => {
		const run = vi.fn(async () => result({ saved: 1 }));
		const relay = await started({ acts: { run }, dialogs: async () => [] });
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "record.save", args: { a: 1 } });
		await settle();

		expect(run).toHaveBeenCalledWith("record.save", { a: 1 });
		expect(replies()).toEqual([{ call_id: "c1", tab: "tab1", result: result({ saved: 1 }), final: true }]);
	});

	it("posts waiting_for_user at once and the end when the person answers", async () => {
		let answer!: (value: unknown) => void;
		const waiting = { ok: false, error: { code: "waiting_for_user", message: "", call: 7 }, route: "/", dialogs: [] };
		const relay = await started({
			acts: { run: async () => waiting, wait: vi.fn(() => new Promise((resolve) => (answer = resolve))) },
		});
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "record.submit" });
		await settle();
		expect(replies().map((reply) => reply.final)).toEqual([false]);

		answer(result("submitted"));
		await settle();
		expect(replies().map((reply) => reply.final)).toEqual([false, true]);
		expect(replies()[1].result.data).toBe("submitted");
	});

	it("does not hand a second run the first confirm's end", async () => {
		let answer!: (value: unknown) => void;
		const waiting = { ok: false, error: { code: "waiting_for_user", message: "", call: 9 }, route: "/", dialogs: [] };
		const wait = vi.fn(() => new Promise((resolve) => (answer = resolve)));
		// `window.desk` gives a second run the open confirm's result and starts nothing.
		const relay = await started({ acts: { run: async () => waiting, wait } });
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "record.submit" });
		relay.emit({ call_id: "c2", op: "run", tab: "tab1", act: "list.refresh" });
		await settle();

		const second = replies().find((reply) => reply.call_id === "c2");
		expect(second.result.error.code).toBe("failed");
		expect(second.final).toBe(true);
		expect(wait).toHaveBeenCalledTimes(1);

		answer(result("submitted"));
		await settle();
		expect(replies().filter((reply) => reply.call_id === "c2")).toHaveLength(1);
		expect(replies().find((reply) => reply.call_id === "c1" && reply.final).result.data).toBe("submitted");
	});

	it("posts a failed end when waiting on the confirm throws, and keeps answering", async () => {
		const waiting = { ok: false, error: { code: "waiting_for_user", message: "", call: 11 }, route: "/", dialogs: [] };
		const relay = await started({
			acts: { run: async () => waiting, wait: async () => Promise.reject(new Error("gone")) },
			state: async () => ({}),
		});
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "record.submit" });
		await settle();
		const end = replies().find((reply) => reply.call_id === "c1" && reply.final);
		expect(end.result.error.code).toBe("failed");

		relay.emit({ call_id: "c3", op: "state", tab: "tab1" });
		await settle();
		expect(replies().some((reply) => reply.call_id === "c3")).toBe(true);
	});

	it("answers calls one at a time, in order", async () => {
		const order: string[] = [];
		const run = vi.fn(async (act: string) => {
			order.push(`start ${act}`);
			await settle();
			order.push(`end ${act}`);
			return result(act);
		});
		const relay = await started({ acts: { run }, dialogs: async () => [] });
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "one" });
		relay.emit({ call_id: "c2", op: "run", tab: "tab1", act: "two" });
		await settle();
		await settle();
		await settle();

		expect(order).toEqual(["start one", "end one", "start two", "end two"]);
	});

	it("lists the acts of one surface and reads the state and dialogs", async () => {
		const list = async () => [{ surface: "list", name: "list.a" }, { surface: "record", name: "record.b" }];
		const relay = await started({ acts: { list }, state: async () => ({ page: "list" }), dialogs: async () => [] });
		relay.emit({ call_id: "c1", op: "acts", tab: "tab1", args: { surface: "record" } });
		relay.emit({ call_id: "c2", op: "state", tab: "tab1" });
		relay.emit({ call_id: "c3", op: "dialogs", tab: "tab1" });
		await settle();
		await settle();
		await settle();

		expect(replies().map((reply) => reply.result.data)).toEqual([[{ surface: "record", name: "record.b" }], { page: "list" }, []]);
	});

	it("answers `failed` when window.desk is missing, and `invalid` when run has no act", async () => {
		const relay = await started({ acts: {}, dialogs: async () => [] });
		relay.emit({ call_id: "c1", op: "run", tab: "tab1" });
		await settle();

		expect(replies()[0].result.error.code).toBe("invalid");
	});
});

describe("the tab id", () => {
	it("keeps the stored id across a reload", async () => {
		expect(await claimTabId()).toBe("tab1");
	});

	it("makes a new id for a tab opened from another", async () => {
		const opener = vi.spyOn(window, "opener", "get").mockReturnValue({} as Window);
		expect(await claimTabId()).not.toBe("tab1");
		opener.mockRestore();
	});

	it("keeps its id on a reload even with an opener", async () => {
		const opener = vi.spyOn(window, "opener", "get").mockReturnValue({} as Window);
		const nav = vi.spyOn(performance, "getEntriesByType").mockReturnValue([{ type: "reload" }] as any);
		expect(await claimTabId()).toBe("tab1");
		opener.mockRestore();
		nav.mockRestore();
	});

	it("makes a new id when another tab holds the same one", async () => {
		const channels: any[] = [];
		class FakeChannel {
			onmessage: ((event: { data: unknown }) => void) | null = null;
			constructor() {
				channels.push(this);
			}
			postMessage(data: any) {
				// The other tab holds "tab1" and answers a claim for it.
				if (data.type === "claim" && data.id === "tab1") queueMicrotask(() => this.onmessage?.({ data: { type: "taken", id: "tab1" } }));
			}
		}
		vi.stubGlobal("BroadcastChannel", FakeChannel);
		const id = await claimTabId();

		expect(id).not.toBe("tab1");
		expect(sessionStorage.getItem("desk-tab")).toBe(id);
	});
});
