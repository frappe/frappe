// The shell writes each list and record visit to Route History, debounced, kept alive, and flushed when the tab hides.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { recordRouteHistory } from "@/shell/routeHistory";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));
vi.mock("@framework/ui/api", () => ({ runMethod: fake.runMethod }));

const METHOD = "frappe.desk.doctype.route_history.route_history.deferred_insert";
const Page = { render: () => null };

let router: Router;

beforeEach(() => {
	vi.useFakeTimers();
	fake.runMethod.mockReset().mockResolvedValue({ data: null });
	router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: Page },
			{ path: "/:doctype", name: "list", component: Page },
			{ path: "/:doctype/new", name: "new-record", component: Page },
			{ path: "/:doctype/:name", name: "record", component: Page },
		],
	});
	recordRouteHistory(router, "/base");
});

afterEach(() => {
	vi.useRealTimers();
	setVisibility("visible");
});

function setVisibility(state: DocumentVisibilityState) {
	Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
	document.dispatchEvent(new Event("visibilitychange"));
}

function sent() {
	return fake.runMethod.mock.calls.map(([method, args, options]) => {
		expect(options.keepalive).toBe(true);
		return [method, args.routes.map((row: { route: string }) => row.route)];
	});
}

describe("route history", () => {
	it("sends the list and record addresses visited, once ten seconds pass with no visit", async () => {
		await router.push("/todo");
		await router.push("/todo/new");
		await router.push("/todo/TODO%2F1");
		await vi.advanceTimersByTimeAsync(9_999);
		expect(fake.runMethod).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(1);
		expect(sent()).toEqual([
			[METHOD, ["/base/todo", "/base/todo/TODO%2F1"]],
		]);
	});

	it("skips the home address and a change of query on the same page", async () => {
		await router.push("/");
		await router.push("/todo");
		await router.push("/todo?view=open");
		await vi.advanceTimersByTimeAsync(10_000);
		expect(sent()).toEqual([[METHOD, ["/base/todo"]]]);
	});

	it("sends what is queued at once when the tab hides, and nothing twice", async () => {
		await router.push("/todo/t1");
		setVisibility("hidden");
		expect(sent()).toEqual([[METHOD, ["/base/todo/t1"]]]);
		await vi.advanceTimersByTimeAsync(10_000);
		setVisibility("hidden");
		expect(fake.runMethod).toHaveBeenCalledTimes(1);
	});

	it("drops a batch the server refuses", async () => {
		fake.runMethod.mockRejectedValueOnce(new Error("read only"));
		await router.push("/todo/t1");
		await vi.advanceTimersByTimeAsync(10_000);
		await router.push("/todo/t2");
		await vi.advanceTimersByTimeAsync(10_000);
		expect(sent()[1]).toEqual([METHOD, ["/base/todo/t2"]]);
	});
});
