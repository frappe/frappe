// The record's `docinfo` kept live over its realtime room.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { applyDocinfoUpdate, isForRecord, useLiveDocinfo } from "../liveDocinfo";

type Handler = (...args: unknown[]) => void;

class FakeSocket {
	emitted: unknown[][] = [];
	handlers = new Map<string, Handler[]>();

	emit(event: string, ...args: unknown[]) {
		this.emitted.push([event, ...args]);
	}
	on(event: string, handler: Handler) {
		this.handlers.set(event, [...(this.handlers.get(event) ?? []), handler]);
	}
	off(event: string, handler: Handler) {
		this.handlers.set(
			event,
			(this.handlers.get(event) ?? []).filter((one) => one !== handler)
		);
	}
	fire(event: string, ...args: unknown[]) {
		for (const handler of this.handlers.get(event) ?? []) handler(...args);
	}
	listeners(event: string) {
		return this.handlers.get(event)?.length ?? 0;
	}
}

const delta = (key: string, doc: Record<string, any>, action?: "add" | "update" | "delete") => ({
	key,
	action,
	doc: { reference_doctype: "Lead", reference_name: "L-1", ...doc },
});

function setup() {
	const socket = new FakeSocket();
	const docinfo = ref<Record<string, any> | null>({ comments: [], assignments: [] });
	const reload = vi.fn(async () => {});
	const live = useLiveDocinfo({ socket, docinfo, reload });
	return { socket, docinfo, reload, live };
}

describe("useLiveDocinfo", () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it("joins the record's room once followed, and leaves it when disposed", () => {
		const { socket, live } = setup();
		expect(socket.emitted).toEqual([]);
		live.follow("Lead", "L-1");
		expect(socket.emitted).toEqual([["doc_subscribe", "Lead", "L-1"]]);
		expect(socket.listeners("docinfo_update")).toBe(1);
		live.dispose();
		expect(socket.emitted.at(-1)).toEqual(["doc_unsubscribe", "Lead", "L-1"]);
		expect(socket.listeners("docinfo_update")).toBe(0);
		// The one left is the socket module's own: it rejoins held rooms after a reconnect.
		expect(socket.listeners("connect")).toBe(1);
		expect(socket.listeners("disconnect")).toBe(0);
	});

	it("moves rooms on a route change with one set of listeners", () => {
		const { socket, live } = setup();
		live.follow("Lead", "L-1");
		live.follow("Lead", "L-2");
		expect(socket.emitted).toEqual([
			["doc_subscribe", "Lead", "L-1"],
			["doc_unsubscribe", "Lead", "L-1"],
			["doc_subscribe", "Lead", "L-2"],
		]);
		expect(socket.listeners("docinfo_update")).toBe(1);
		live.dispose();
	});

	it("splices a comment delta into its bucket and ignores another record's", () => {
		const { socket, docinfo, live } = setup();
		live.follow("Lead", "L-1");
		socket.fire("docinfo_update", delta("comments", { name: "c1", content: "hi" }, "add"));
		expect(docinfo.value!.comments).toEqual([
			{ reference_doctype: "Lead", reference_name: "L-1", name: "c1", content: "hi" },
		]);
		socket.fire("docinfo_update", {
			...delta("comments", { name: "c9" }, "add"),
			doc: { reference_doctype: "Lead", reference_name: "L-2", name: "c9" },
		});
		expect(docinfo.value!.comments).toHaveLength(1);
		live.dispose();
	});

	it("re-reads the sidecar once for a burst of assignment logs", async () => {
		const { socket, docinfo, reload, live } = setup();
		live.follow("Lead", "L-1");
		socket.fire("docinfo_update", delta("assignment_logs", { name: "a1" }, "add"));
		socket.fire("docinfo_update", delta("assignment_logs", { name: "a2" }, "add"));
		// The page holds no log bucket; the delta only says "re-read".
		expect(docinfo.value).toEqual({ comments: [], assignments: [] });
		expect(reload).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(250);
		expect(reload).toHaveBeenCalledTimes(1);
		live.dispose();
	});

	it("re-reads instead of splicing a share, a tag or a favourite", async () => {
		const { socket, docinfo, reload, live } = setup();
		docinfo.value = { shares: [], tags: [], favourites: [] };
		live.follow("Lead", "L-1");
		socket.fire("docinfo_update", delta("shared", { name: "s1", user: "a@x.io" }, "add"));
		socket.fire("docinfo_update", delta("tags", { name: "t1", tag: "hot" }, "add"));
		socket.fire("docinfo_update", delta("favourites", { name: "f1", user: "a@x.io" }, "add"));
		// The published rows are not the parts' rows; the re-read brings the real ones.
		expect(docinfo.value).toEqual({ shares: [], tags: [], favourites: [] });
		await vi.advanceTimersByTimeAsync(250);
		expect(reload).toHaveBeenCalledTimes(1);
		live.dispose();
	});

	it("does not re-read for a comment", async () => {
		const { socket, reload, live } = setup();
		live.follow("Lead", "L-1");
		socket.fire("docinfo_update", delta("comments", { name: "c1" }, "add"));
		await vi.advanceTimersByTimeAsync(250);
		expect(reload).not.toHaveBeenCalled();
		live.dispose();
	});

	it("re-reads once getdoc lands when a delta arrived while it was in flight", () => {
		const { socket, docinfo, reload, live } = setup();
		docinfo.value = null;
		live.follow("Lead", "L-1");
		socket.fire("docinfo_update", delta("comments", { name: "c1" }, "add"));
		expect(docinfo.value).toBeNull();
		expect(reload).not.toHaveBeenCalled();
		docinfo.value = { comments: [] };
		expect(reload).toHaveBeenCalledTimes(1);
		docinfo.value = { comments: [{ name: "c1" }] };
		expect(reload).toHaveBeenCalledTimes(1);
		live.dispose();
	});

	it("forgets a delta held for a record the route left", () => {
		const { socket, docinfo, reload, live } = setup();
		docinfo.value = null;
		live.follow("Lead", "L-1");
		socket.fire("docinfo_update", delta("comments", { name: "c1" }, "add"));
		live.follow("Lead", "L-2");
		docinfo.value = { comments: [] };
		expect(reload).not.toHaveBeenCalled();
		live.dispose();
	});

	it("skips a scheduled re-read once the route has moved on", async () => {
		const { socket, reload, live } = setup();
		live.follow("Lead", "L-1");
		socket.fire("docinfo_update", delta("assignment_logs", { name: "a1" }, "add"));
		live.follow("Lead", "L-2");
		await vi.advanceTimersByTimeAsync(250);
		expect(reload).not.toHaveBeenCalled();
		live.dispose();
	});

	it("re-reads after a dropped connection, not on the first connect, and leaves rejoining to the socket", () => {
		const { socket, reload, live } = setup();
		live.follow("Lead", "L-1");
		socket.fire("connect");
		expect(reload).not.toHaveBeenCalled();
		socket.fire("disconnect");
		socket.fire("connect");
		expect(reload).toHaveBeenCalledTimes(1);
		expect(socket.emitted.filter(([event]) => event === "doc_subscribe")).toHaveLength(1);
		live.dispose();
	});

	it("re-reads on demand for the record it follows", () => {
		const { reload, live } = setup();
		live.follow("Lead", "L-1");
		live.reloadQuietly();
		expect(reload).toHaveBeenCalledTimes(1);
		live.dispose();
	});

	it("survives a re-read that fails", async () => {
		const { socket, reload, live } = setup();
		reload.mockRejectedValueOnce(new Error("Sidecar down"));
		vi.spyOn(console, "warn").mockImplementation(() => {});
		live.follow("Lead", "L-1");
		socket.fire("disconnect");
		socket.fire("connect");
		await vi.advanceTimersByTimeAsync(0);
		expect(reload).toHaveBeenCalledTimes(1);
		live.dispose();
	});

	it("does nothing without a socket", () => {
		const docinfo = ref<Record<string, any> | null>({});
		const live = useLiveDocinfo({ socket: undefined, docinfo, reload: async () => {} });
		live.follow("Lead", "L-1");
		live.dispose();
		expect(docinfo.value).toEqual({});
	});
});

describe("applyDocinfoUpdate", () => {
	const docinfo = { comments: [{ name: "c1", content: "old" }], tags: "a,b" };

	it("adds, replaces and removes by name, leaving other buckets alone", () => {
		const added = applyDocinfoUpdate(docinfo, delta("comments", { name: "c2" }, "add"));
		expect(added.comments.map((row) => row.name)).toEqual(["c1", "c2"]);
		expect(added.tags).toBe("a,b");
		const replaced = applyDocinfoUpdate(
			added,
			delta("comments", { name: "c1", content: "new" })
		);
		expect(replaced.comments[0].content).toBe("new");
		const removed = applyDocinfoUpdate(replaced, delta("comments", { name: "c1" }, "delete"));
		expect(removed.comments.map((row) => row.name)).toEqual(["c2"]);
	});

	it("never adds a row twice, and leaves an update for an unknown row alone", () => {
		const twice = applyDocinfoUpdate(docinfo, delta("comments", { name: "c1" }, "add"));
		expect(twice.comments).toHaveLength(1);
		const unknown = applyDocinfoUpdate(docinfo, delta("comments", { name: "zz" }));
		expect(unknown.comments).toEqual(docinfo.comments);
	});

	it("never adds a bucket the page does not hold", () => {
		const same = applyDocinfoUpdate(docinfo, delta("like_logs", { name: "l1" }, "add"));
		expect(same).toBe(docinfo);
	});
});

describe("isForRecord", () => {
	it("matches on the delta's reference, not on the socket room", () => {
		const target = { doctype: "Lead", docname: "L-1" };
		expect(isForRecord(delta("comments", { name: "c1" }), target)).toBe(true);
		expect(isForRecord(delta("comments", { name: "c1" }), { ...target, docname: "L-2" })).toBe(false);
		expect(isForRecord({ key: "comments", doc: undefined as any }, target)).toBe(false);
	});
});
