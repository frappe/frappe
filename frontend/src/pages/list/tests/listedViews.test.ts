// The listed views hook: one read per open, the same answer remembered, a failed first read asked
// again by the next menu open, and a write to a view read again.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick } from "vue";
import { refreshSavedViews } from "@/list/savedView";
import { resetListedViews, useListedViews, type ListedView } from "@/list/listedViews";

const fetchViews = vi.hoisted(() => vi.fn());
vi.mock("@/navigation/editor/viewPicker", () => ({ fetchViews }));
vi.mock("@framework/ui/useSession", () => ({ currentSession: () => ({ user: { name: "a@example.com" } }) }));

const VIEW: ListedView = { key: "list", label: "List", type: "List", layer: null };
const flush = async () => {
	await Promise.resolve();
	await nextTick();
	await Promise.resolve();
};

const scopes: ReturnType<typeof effectScope>[] = [];

function open() {
	const scope = effectScope();
	scopes.push(scope);
	const hook = scope.run(() => useListedViews("ToDo", "frappe"))!;
	return { hook, stop: () => scope.stop() };
}

afterEach(() => scopes.splice(0).forEach((scope) => scope.stop()));

beforeEach(() => {
	resetListedViews();
	fetchViews.mockReset();
});

describe("useListedViews", () => {
	it("reads once on open and keeps the answer", async () => {
		fetchViews.mockResolvedValue([VIEW]);
		const { hook } = open();
		await flush();
		expect(fetchViews).toHaveBeenCalledTimes(1);
		expect(hook.views.value).toEqual([VIEW]);
	});

	it("paints the remembered answer at once on a second open", async () => {
		fetchViews.mockResolvedValue([VIEW]);
		open();
		await flush();
		const second = open();
		expect(second.hook.views.value).toEqual([VIEW]);
	});

	it("stays empty after a failed first read, and reload asks again", async () => {
		fetchViews.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([VIEW]);
		const { hook } = open();
		await flush();
		expect(hook.views.value).toBeNull();
		await hook.reload();
		expect(hook.views.value).toEqual([VIEW]);
	});

	it("reads again after a write to a view", async () => {
		fetchViews.mockResolvedValue([VIEW]);
		open();
		await flush();
		refreshSavedViews();
		await flush();
		expect(fetchViews).toHaveBeenCalledTimes(2);
	});

	it("drops an answer that lands after the scope ended", async () => {
		let resolve!: (views: ListedView[]) => void;
		fetchViews.mockReturnValue(new Promise((done) => (resolve = done)));
		const { hook, stop } = open();
		stop();
		resolve([VIEW]);
		await flush();
		expect(hook.views.value).toBeNull();
	});
});
