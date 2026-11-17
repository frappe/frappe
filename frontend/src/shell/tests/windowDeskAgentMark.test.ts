// The mark that shows an agent driving the tab, and Stop: pending calls end `interrupted`, later ones are refused.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp } from "vue";

const runMethod = vi.fn(async (..._args: unknown[]) => ({ data: null }));
vi.mock("@framework/ui/api", () => ({ runMethod: (...args: unknown[]) => runMethod(...args) }));

import { AgentMark } from "../windowDesk/agentMark";
import { startRelay } from "../windowDesk/relay";

type Handler = (event: unknown) => void;

function socket() {
	const handlers: Handler[] = [];
	return { on: (_name: string, handler: Handler) => handlers.push(handler), off: vi.fn(), emit: (event: unknown) => handlers.forEach((handler) => handler(event)) };
}

const result = (data: unknown) => ({ ok: true, data, route: "/apps/x", dialogs: [] });
const replies = () => runMethod.mock.calls.map(([, body]) => body as any);
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const mark = () => document.querySelector<HTMLElement>("[data-agent-mark]");
// The first import of the component pulls in frappe-ui, which takes seconds to transform.
const shown = () => vi.waitFor(() => expect(mark()).not.toBeNull(), { timeout: 30_000 });

async function started(desk: Record<string, unknown>) {
	Object.defineProperty(window, "desk", { value: desk, configurable: true, writable: true });
	const relay = socket();
	const app = createApp({})._context;
	app.config.globalProperties.$socket = relay;
	await startRelay(app);
	return relay;
}

beforeEach(() => {
	sessionStorage.clear();
	sessionStorage.setItem("desk-tab", "tab1");
	runMethod.mockClear();
	vi.stubGlobal("BroadcastChannel", undefined);
});
afterEach(() => {
	delete (window as any).desk;
	document.body.innerHTML = "";
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe("the mark's states", () => {
	it("runs while calls are open, lingers 30 s after the last, then hides", () => {
		vi.useFakeTimers();
		const agent = new AgentMark(vi.fn());
		expect(agent.state.value).toBe("hidden");

		agent.driving("frappectl");
		expect([agent.state.value, agent.client.value]).toEqual(["running", "frappectl"]);

		agent.idle();
		vi.advanceTimersByTime(29_999);
		expect(agent.state.value).toBe("idle");
		vi.advanceTimersByTime(1);
		expect(agent.state.value).toBe("hidden");
	});

	it("a call in the linger window brings it back to running and cancels the hide", () => {
		vi.useFakeTimers();
		const agent = new AgentMark(vi.fn());
		agent.idle();
		vi.advanceTimersByTime(20_000);
		agent.driving(null);
		vi.advanceTimersByTime(60_000);
		expect(agent.state.value).toBe("running");
	});

	it("Stop tells the relay, and shows the stopped state for 30 s", () => {
		vi.useFakeTimers();
		const onStop = vi.fn();
		const agent = new AgentMark(onStop);
		agent.driving("frappectl");
		agent.stop();
		expect(onStop).toHaveBeenCalledOnce();
		expect(agent.state.value).toBe("stopped");
		vi.advanceTimersByTime(30_000);
		expect(agent.state.value).toBe("hidden");
	});
});

describe("the mark in the tab", { timeout: 40_000 }, () => {
	it("is not on the page until the first call, then names the client", async () => {
		const relay = await started({ acts: { run: async () => result(1) }, dialogs: async () => [] });
		relay.emit({ call_id: "hello", op: "tabs" });
		await settle();
		expect(mark()).toBeNull();

		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "x", client: "frappectl" });
		await shown();
		expect(mark()!.textContent).toContain("frappectl is driving this tab");
		expect(mark()!.querySelector("button")!.textContent).toContain("Stop");
	});

	it("names an agent when the token has no OAuth client", async () => {
		const relay = await started({ acts: { run: async () => result(1) }, dialogs: async () => [] });
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "x", client: null });
		await shown();
		expect(mark()!.textContent).toContain("An agent is driving this tab");
	});

	it("does not show for a call to another tab", async () => {
		const relay = await started({ acts: { run: async () => result(1) }, dialogs: async () => [] });
		relay.emit({ call_id: "c1", op: "run", tab: "other", act: "x", client: "frappectl" });
		await settle();
		expect(mark()).toBeNull();
	});
});

describe("Stop", { timeout: 40_000 }, () => {
	const hang = () => ({ acts: { run: () => new Promise(() => {}) }, dialogs: async () => [], state: async () => ({}) });

	it("ends the open call with `interrupted` and refuses the next one", async () => {
		const relay = await started(hang());
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "x", client: "frappectl" });
		await shown();
		mark()!.querySelector("button")!.click();
		await settle();

		const ended = replies().find((reply) => reply.call_id === "c1");
		expect(ended).toMatchObject({ final: true, result: { ok: false, error: { code: "interrupted" } } });
		expect(mark()!.textContent).toContain("Stopped.");
		expect(mark()!.querySelector("button")).toBeNull();

		runMethod.mockClear();
		relay.emit({ call_id: "c2", op: "state", tab: "tab1", client: "frappectl" });
		await settle();
		expect(replies()).toHaveLength(1);
		expect(replies()[0]).toMatchObject({ call_id: "c2", final: true, result: { error: { code: "interrupted" } } });
		expect(mark()!.textContent).toContain("Stopped.");
	});

	it("drops the late end of a parked confirm, which Stop already ended", async () => {
		let answer!: (value: unknown) => void;
		const waiting = { ok: false, error: { code: "waiting_for_user", message: "", call: 7 }, route: "/", dialogs: [] };
		const relay = await started({
			acts: { run: async () => waiting, wait: () => new Promise((resolve) => (answer = resolve)) },
			dialogs: async () => [],
		});
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "record.submit", client: "frappectl" });
		await shown();
		await settle();
		mark()!.querySelector("button")!.click();
		await settle();
		answer(result("submitted"));
		await settle();

		expect(replies().filter((reply) => reply.call_id === "c1").map((reply) => reply.final)).toEqual([false, true]);
		expect(replies().at(-1).result.error.code).toBe("interrupted");
	});

	it("skips a call that was queued behind the one Stop ended", async () => {
		const run = vi.fn(() => new Promise(() => {}));
		const relay = await started({ acts: { run }, dialogs: async () => [] });
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "one", client: "frappectl" });
		relay.emit({ call_id: "c2", op: "run", tab: "tab1", act: "two", client: "frappectl" });
		await shown();
		mark()!.querySelector("button")!.click();
		await settle();

		expect(run).toHaveBeenCalledTimes(1);
		expect(replies().filter((reply) => reply.result.error?.code === "interrupted").map((reply) => reply.call_id).sort()).toEqual(["c1", "c2"]);
	});

	it("still answers a hello, and shows the stopped pill again when it refuses a call after the 30 s", async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		const relay = await started(hang());
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "x", client: "frappectl" });
		await shown();
		mark()!.querySelector("button")!.click();
		await vi.advanceTimersByTimeAsync(30_000);
		await vi.waitFor(() => expect(mark()).toBeNull());
		runMethod.mockClear();

		relay.emit({ call_id: "hello", op: "tabs" });
		await vi.advanceTimersByTimeAsync(0);
		expect(replies()[0]).toMatchObject({ call_id: "hello", result: { tab: "tab1" } });

		relay.emit({ call_id: "c2", op: "state", tab: "tab1", client: "frappectl" });
		await vi.advanceTimersByTimeAsync(0);
		await vi.waitFor(() => expect(mark()!.textContent).toContain("Stopped."));
	});

	it("drops the late result of an act that was running when Stop ended its call", async () => {
		let finish!: (value: unknown) => void;
		const relay = await started({ acts: { run: () => new Promise((resolve) => (finish = resolve)) }, dialogs: async () => [] });
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "x", client: "frappectl" });
		await shown();
		await vi.waitFor(() => expect(finish).toBeDefined());
		mark()!.querySelector("button")!.click();
		await settle();
		runMethod.mockClear();

		finish(result({ saved: true }));
		await settle();
		expect(runMethod).not.toHaveBeenCalled();
	});

	it("names an agent that still has a call open when another one ends", async () => {
		const waiting = { ok: false, error: { code: "waiting_for_user", message: "Ask", call: 3 }, route: "/", dialogs: [] };
		const desk = {
			acts: { run: async () => waiting, wait: () => new Promise(() => {}) },
			dialogs: async () => [],
			state: async () => ({}),
		};
		const relay = await started(desk);
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "x", client: "agent-a" });
		await shown();
		relay.emit({ call_id: "c2", op: "state", tab: "tab1", client: "agent-b" });
		await vi.waitFor(() => expect(replies().some((reply) => reply.call_id === "c2" && reply.final)).toBe(true));
		expect(mark()!.textContent).toContain("agent-a");
	});

	it("a call whose act throws ends and lets the mark go idle", async () => {
		const relay = await started({ acts: { run: async () => { throw new Error("boom"); } }, dialogs: async () => [] });
		relay.emit({ call_id: "c1", op: "run", tab: "tab1", act: "x", client: "frappectl" });
		await shown();
		await vi.waitFor(() => expect(replies().some((reply) => reply.call_id === "c1" && reply.final)).toBe(true));
		expect(replies().at(-1).result.error.code).toBe("failed");
		expect(mark()!.querySelector("button")).not.toBeNull();
		expect(mark()!.textContent).toContain("frappectl");
	});
});

describe("when the mark cannot load", () => {
	it("refuses the call that would run without it, and tries again on the next", async () => {
		vi.resetModules();
		let broken = true;
		vi.doMock("../windowDesk/AgentMark.vue", () => {
			if (broken) throw new Error("chunk failed");
			return { default: { render: () => null } };
		});
		const { RelayCalls } = await import("../windowDesk/relayCalls");
		const calls = new RelayCalls(undefined, vi.fn());
		await expect(calls.ready()).rejects.toThrow();
		broken = false;
		await expect(calls.ready()).resolves.toBeUndefined();
		vi.doUnmock("../windowDesk/AgentMark.vue");
	});
});
