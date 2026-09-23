// The feed scroller: it opens at the bottom, pages older rows near the top, and holds the view while they land.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, reactive } from "vue";
import RecordFeed from "../RecordFeed.vue";

const apps: ReturnType<typeof createApp>[] = [];
const resizeCallbacks: Array<() => void> = [];
const ROW = 100;

// happy-dom never reports a resize, so the test says when the content grew.
class FakeResizeObserver {
	constructor(callback: () => void) {
		resizeCallbacks.push(callback);
	}
	observe() {}
	unobserve() {}
	disconnect() {}
}

beforeEach(() => vi.stubGlobal("ResizeObserver", FakeResizeObserver));
afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	resizeCallbacks.length = 0;
	vi.unstubAllGlobals();
});

interface Geometry {
	scrollTop: number;
	scrollHeight: number;
	clientHeight: number;
}

async function mount(openAtBottom = true, ready = true) {
	const state = reactive({ ready, error: null as unknown, rows: 0 });
	const paginate = reactive({
		hasNextPage: true,
		isFetchingNextPage: false,
		fetchNextPage: vi.fn(() => new Promise<void>(() => {})),
	});
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({
		render: () =>
			h(
				RecordFeed,
				{ paginate, error: state.error, ready: state.ready, openAtBottom },
				() => Array.from({ length: state.rows }, () => h("p", { "data-row": "" }, "row"))
			),
	});
	app.mount(root);
	apps.push(app);
	await nextTick();
	const scroller = root.querySelector<HTMLElement>(
		"[data-record-feed] [data-reka-scroll-area-viewport]"
	)!;
	return { root, state, paginate, scroller, geometry: fake(scroller) };
}

// happy-dom lays nothing out, so the scroller's measurements are stated; each drawn row adds `ROW`.
function fake(element: HTMLElement): Geometry {
	const geometry = { scrollTop: 0, scrollHeight: 0, clientHeight: 0 };
	const drawn = () => element.querySelectorAll("[data-row]").length * ROW;
	Object.defineProperty(element, "scrollHeight", { get: () => geometry.scrollHeight + drawn() });
	Object.defineProperty(element, "clientHeight", { get: () => geometry.clientHeight });
	Object.defineProperty(element, "scrollTop", {
		get: () => geometry.scrollTop,
		set: (value: number) => (geometry.scrollTop = value),
	});
	return geometry;
}

function scrollTo(scroller: HTMLElement, geometry: Geometry, top: number) {
	geometry.scrollTop = top;
	scroller.dispatchEvent(new Event("scroll"));
}

function resize() {
	for (const callback of resizeCallbacks) callback();
}

describe("RecordFeed", () => {
	// The scroll area's root sets an inline `position: relative`, which beats a positioning class.
	it("sizes the scroller from a wrapper, not from the scroll area's root", async () => {
		const { root } = await mount();
		const area = root.querySelector<HTMLElement>('[data-record-feed] [data-slot="scroll-area"]')!;

		expect(area.parentElement!.classList).toContain("absolute");
		expect(area.parentElement!.classList).toContain("inset-0");
		const positions = ["absolute", "fixed", "sticky"];
		expect([...area.classList].filter((name) => positions.includes(name))).toEqual([]);
		expect(area.classList).toContain("h-full");
	});

	it("opens at the bottom once the first rows are drawn", async () => {
		const { state, geometry } = await mount(true, false);
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });

		state.ready = true;
		await nextTick();

		expect(geometry.scrollTop).toBe(3000);
	});

	it("reads the older page one screen from the top, and not before", async () => {
		const { paginate, scroller, geometry } = await mount();
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });

		scrollTo(scroller, geometry, 1200);
		expect(paginate.fetchNextPage).not.toHaveBeenCalled();

		scrollTo(scroller, geometry, 400);
		expect(paginate.fetchNextPage).toHaveBeenCalledTimes(1);
	});

	it("holds the reader's view while the older page lands above it", async () => {
		const { state, paginate, scroller, geometry } = await mount();
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });
		scrollTo(scroller, geometry, 400);

		paginate.isFetchingNextPage = true;
		await nextTick();
		state.rows = 12;
		paginate.isFetchingNextPage = false;
		await nextTick();

		expect(geometry.scrollTop).toBe(1600);
	});

	it("keeps the reader where they scrolled to while the older page was read", async () => {
		const { state, paginate, scroller, geometry } = await mount();
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });
		scrollTo(scroller, geometry, 400);
		paginate.isFetchingNextPage = true;
		await nextTick();

		scrollTo(scroller, geometry, 250);
		state.rows = 12;
		paginate.isFetchingNextPage = false;
		await nextTick();

		expect(geometry.scrollTop).toBe(1450);
	});

	it("counts a scroll whose event has not fired yet when the older page lands", async () => {
		const { state, paginate, scroller, geometry } = await mount();
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });
		scrollTo(scroller, geometry, 400);
		paginate.isFetchingNextPage = true;
		await nextTick();

		geometry.scrollTop = 250;
		state.rows = 12;
		paginate.isFetchingNextPage = false;
		await nextTick();

		expect(geometry.scrollTop).toBe(1450);
	});

	it("does not undo the reader's scroll when a row resizes during the read", async () => {
		const { paginate, scroller, geometry } = await mount();
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });
		scrollTo(scroller, geometry, 400);
		paginate.isFetchingNextPage = true;
		await nextTick();

		scrollTo(scroller, geometry, 250);
		resize();

		expect(geometry.scrollTop).toBe(250);
	});

	it("follows content that grows after landing, when the landing scroll reports late", async () => {
		const { state, scroller, geometry } = await mount(true, false);
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });
		state.ready = true;
		await nextTick();

		geometry.scrollHeight = 4000;
		scroller.dispatchEvent(new Event("scroll"));
		resize();

		expect(geometry.scrollTop).toBe(4000);
	});

	it("lets go of the bottom when the reader scrolls up, and takes it back at the bottom", async () => {
		const { state, scroller, geometry } = await mount(true, false);
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });
		state.ready = true;
		await nextTick();

		scrollTo(scroller, geometry, 2000);
		geometry.scrollHeight = 4000;
		resize();
		expect(geometry.scrollTop).toBe(2000);

		scrollTo(scroller, geometry, 3500);
		geometry.scrollHeight = 4400;
		resize();
		expect(geometry.scrollTop).toBe(4400);
	});

	it("stops paging on scroll after a failed read, and offers a retry", async () => {
		const { root, state, paginate, scroller, geometry } = await mount();
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });
		paginate.fetchNextPage.mockImplementation(async () => {
			state.error = new Error("offline");
		});

		scrollTo(scroller, geometry, 100);
		await nextTick();
		await nextTick();
		scrollTo(scroller, geometry, 50);

		expect(paginate.fetchNextPage).toHaveBeenCalledTimes(1);
		const retry = [...root.querySelectorAll("button")].find((button) =>
			button.textContent?.includes("Load older")
		);
		retry!.click();
		expect(paginate.fetchNextPage).toHaveBeenCalledTimes(2);
	});

	it("reads the next older page at once when one lands with no rows near the top", async () => {
		const { paginate, scroller, geometry } = await mount();
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });
		const reads = storeReads(paginate, 2);

		scrollTo(scroller, geometry, 100);
		await settle();

		expect(reads.started).toBe(2);
	});

	it("waits for a scroll when the reader has moved away before the page lands", async () => {
		const { paginate, scroller, geometry } = await mount();
		Object.assign(geometry, { scrollHeight: 3000, clientHeight: 500 });
		const reads = storeReads(paginate, 2);

		scrollTo(scroller, geometry, 100);
		geometry.scrollTop = 1500;
		await settle();

		expect(reads.started).toBe(1);
	});

	it("never pages from a hidden tab, which has no height", async () => {
		const { paginate, scroller, geometry } = await mount();
		geometry.scrollHeight = 3000;

		scrollTo(scroller, geometry, 0);

		expect(paginate.fetchNextPage).not.toHaveBeenCalled();
	});
});

// The store's shape: calls share one read, which clears only after `isFetchingNextPage` drops.
interface Pages {
	hasNextPage: boolean;
	isFetchingNextPage: boolean;
	fetchNextPage: () => Promise<void>;
}

function storeReads(paginate: Pages, last: number) {
	const reads = { started: 0 };
	let inFlight: Promise<void> | undefined;
	paginate.fetchNextPage = () => {
		if (inFlight) return inFlight;
		reads.started++;
		paginate.isFetchingNextPage = true;
		inFlight = landEmpty().finally(() => (inFlight = undefined));
		return inFlight;
	};
	async function landEmpty() {
		await Promise.resolve();
		paginate.isFetchingNextPage = false;
		if (reads.started === last) paginate.hasNextPage = false;
	}
	return reads;
}

async function settle() {
	for (let tick = 0; tick < 10; tick++) await nextTick();
}
