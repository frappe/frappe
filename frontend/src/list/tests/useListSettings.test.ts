// The settings composable as claims: one fetch per doctype, the layering, the debounced write, and
// the reset. The wrapper's method call is faked; the debounce runs on fake timers.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));

vi.mock("@framework/ui/api", () => ({ runMethod: fake.runMethod }));

import { dropListSettings, resetListSettings, useListSettings, WRITE_DEBOUNCE_MS } from "../useListSettings";

const API = "frappe.desk.doctype.doctype_view.api";
const ADDRESS = { doctype: "Lead", type: "List" };

let tiers: { site: unknown; user: unknown };

function respond(method: string, args: { settings?: Record<string, unknown>; key?: string; scope?: string }) {
	if (method.endsWith(".save")) {
		const row = (tiers[args.scope as "site" | "user"] ?? {}) as Record<string, unknown>;
		tiers = { ...tiers, [args.scope!]: { ...row, ...args.settings } };
	}
	if (method.endsWith(".reset")) {
		const row = { ...(tiers[args.scope as "site" | "user"] as Record<string, unknown>) };
		delete row[args.key!];
		tiers = { ...tiers, [args.scope!]: Object.keys(row).length ? row : null };
	}
	return Promise.resolve({ data: tiers });
}

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await Promise.resolve();
		await nextTick();
	}
}

beforeEach(() => {
	vi.useFakeTimers();
	resetListSettings();
	tiers = { site: { sort: [{ fieldname: "title", direction: "asc" }] }, user: null };
	fake.runMethod.mockReset().mockImplementation(respond);
});

afterEach(() => {
	vi.useRealTimers();
});

describe("reading", () => {
	it("fetches once per doctype and layers the person's row over the site's", async () => {
		const first = useListSettings("Lead");
		const second = useListSettings("Lead");
		expect(first.loaded.value).toBe(false);
		await settle();
		expect(fake.runMethod).toHaveBeenCalledTimes(1);
		expect(fake.runMethod).toHaveBeenCalledWith(`${API}.get`, ADDRESS);
		expect(second.loaded.value).toBe(true);
		expect(second.stored.value).toEqual({ sort: [{ fieldname: "title", direction: "asc" }] });
		expect(first.has("site", "sort")).toBe(true);
		expect(first.has("user", "sort")).toBe(false);
	});

	it("reads a failed fetch as no rows, and is still loaded", async () => {
		fake.runMethod.mockRejectedValue(new Error("down"));
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const handle = useListSettings("Lead");
		await settle();
		expect(handle.loaded.value).toBe(true);
		expect(handle.stored.value).toEqual({});
		warn.mockRestore();
	});
});

describe("writing", () => {
	it("joins patches inside the window into one write and takes the response as the rows", async () => {
		const handle = useListSettings("Lead");
		await settle();
		handle.save({ columns: [{ fieldname: "title" }] });
		handle.save({ sort: [] });
		expect(handle.has("user", "columns")).toBe(true);
		expect(fake.runMethod).toHaveBeenCalledTimes(1);
		vi.advanceTimersByTime(WRITE_DEBOUNCE_MS);
		await settle();
		expect(fake.runMethod).toHaveBeenCalledTimes(2);
		expect(fake.runMethod).toHaveBeenLastCalledWith(`${API}.save`, {
			...ADDRESS,
			scope: "user",
			settings: { columns: [{ fieldname: "title" }], sort: [] },
		});
		expect(handle.stored.value).toEqual({ columns: [{ fieldname: "title" }], sort: [] });
	});

	it("sends a waiting write before a reset, and the reset drops the key from the person's row", async () => {
		const handle = useListSettings("Lead");
		await settle();
		handle.save({ columns: [{ fieldname: "title" }], quick_filter_fields: ["name"] });
		await handle.reset("columns");
		expect(fake.runMethod.mock.calls.map(([method]) => method.split(".").pop())).toEqual(["get", "save", "reset"]);
		expect(fake.runMethod).toHaveBeenLastCalledWith(`${API}.reset`, { ...ADDRESS, scope: "user", key: "columns" });
		expect(handle.has("user", "columns")).toBe(false);
		expect(handle.stored.value).toEqual({
			sort: [{ fieldname: "title", direction: "asc" }],
			quick_filter_fields: ["name"],
		});
	});

	it("keeps a patch whose write failed for the next flush", async () => {
		const handle = useListSettings("Lead");
		await settle();
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		fake.runMethod.mockRejectedValueOnce(new Error("down"));
		handle.save({ columns: [{ fieldname: "title" }] });
		await handle.flush();
		expect(handle.stored.value).toEqual({ sort: [{ fieldname: "title", direction: "asc" }] });
		expect(handle.has("user", "columns")).toBe(true);
		handle.save({ sort: [] });
		await handle.flush();
		expect(fake.runMethod).toHaveBeenLastCalledWith(`${API}.save`, {
			...ADDRESS,
			scope: "user",
			settings: { columns: [{ fieldname: "title" }], sort: [] },
		});
		warn.mockRestore();
	});

	it("does not bring back a key the person reset while its failed write was in flight", async () => {
		const handle = useListSettings("Lead");
		await settle();
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		fake.runMethod.mockRejectedValueOnce(new Error("down"));
		handle.save({ columns: [{ fieldname: "title" }], sort: [] });
		const failing = handle.flush();
		const resetting = handle.reset("columns");
		await Promise.all([failing, resetting]);
		expect(handle.has("user", "columns")).toBe(false);
		expect(handle.has("user", "sort")).toBe(true);
		handle.save({ quick_filter_fields: [] });
		await handle.flush();
		expect(fake.runMethod).toHaveBeenLastCalledWith(`${API}.save`, {
			...ADDRESS,
			scope: "user",
			settings: { sort: [], quick_filter_fields: [] },
		});
		warn.mockRestore();
	});

	it("writes the site scope at once, by name", async () => {
		const handle = useListSettings("Lead");
		await settle();
		await handle.saveForSite({ columns: [{ fieldname: "amount" }] });
		expect(fake.runMethod).toHaveBeenLastCalledWith(`${API}.save`, {
			...ADDRESS,
			scope: "site",
			settings: { columns: [{ fieldname: "amount" }] },
		});
		await handle.resetForSite("sort");
		expect(fake.runMethod).toHaveBeenLastCalledWith(`${API}.reset`, { ...ADDRESS, scope: "site", key: "sort" });
		expect(handle.stored.value).toEqual({ columns: [{ fieldname: "amount" }] });
	});
});

describe("dropping", () => {
	const methods = () => fake.runMethod.mock.calls.map(([method]) => method.split(".").pop());

	it("sends a waiting write at once, and the next caller reads only after it lands", async () => {
		const open = useListSettings("Lead");
		await settle();
		let land = () => {};
		fake.runMethod.mockImplementationOnce(
			(method, args) => new Promise((resolve) => (land = () => resolve(respond(method, args))))
		);
		open.save({ columns: [{ fieldname: "title" }] });
		dropListSettings("Lead");
		const next = useListSettings("Lead");
		await settle();
		expect(methods()).toEqual(["get", "save"]);
		land();
		await settle();
		await settle();
		expect(methods()).toEqual(["get", "save", "get"]);
		expect(next.stored.value).toEqual({
			sort: [{ fieldname: "title", direction: "asc" }],
			columns: [{ fieldname: "title" }],
		});
	});

	it("leaves the open handle on its own rows, still writing", async () => {
		const open = useListSettings("Lead");
		await settle();
		dropListSettings("Lead");
		open.save({ sort: [] });
		vi.advanceTimersByTime(WRITE_DEBOUNCE_MS);
		await settle();
		expect(methods()).toEqual(["get", "save"]);
		expect(open.stored.value).toEqual({ sort: [] });
	});

	it("hands a write that failed after the drop to the next caller", async () => {
		const open = useListSettings("Lead");
		await settle();
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		fake.runMethod.mockRejectedValueOnce(new Error("down"));
		open.save({ columns: [{ fieldname: "title" }] });
		dropListSettings("Lead");
		const next = useListSettings("Lead");
		await settle();
		expect(next.has("user", "columns")).toBe(true);
		await next.flush();
		expect(fake.runMethod).toHaveBeenLastCalledWith(`${API}.save`, {
			...ADDRESS,
			scope: "user",
			settings: { columns: [{ fieldname: "title" }] },
		});
		warn.mockRestore();
	});

	it("keeps every other doctype's rows", async () => {
		useListSettings("Lead");
		useListSettings("Deal");
		await settle();
		dropListSettings("Deal");
		useListSettings("Lead");
		await settle();
		expect(methods()).toEqual(["get", "get"]);
	});
});
