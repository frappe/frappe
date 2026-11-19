// When a page's code is imported: after the frame has painted, or at once before the first paint.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { createMemoryHistory, createRouter, RouterView } from "vue-router";

import { clearLoadedPages, loadedPage } from "@/router/mainPage";

const page = defineComponent({ render: () => h("div", { "data-page": "" }) });

let frames: FrameRequestCallback[] = [];

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

/** Runs the frame the browser would paint next. */
async function paint() {
	for (const frame of frames.splice(0)) frame(performance.now());
	await settle();
}

async function open(loader: () => Promise<unknown>) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/", component: loadedPage(loader) }],
	});
	await router.push("/");
	const host = document.createElement("div");
	document.body.appendChild(host);
	createApp(defineComponent({ render: () => h(RouterView) }))
		.use(router)
		.mount(host);
	await settle();
	return host;
}

/** Whether the document has painted content, as `first-contentful-paint` says. */
function painted(value: boolean) {
	const entries = value ? [{ name: "first-contentful-paint" }] : [];
	vi.spyOn(performance, "getEntriesByName").mockReturnValue(entries as PerformanceEntryList);
}

beforeEach(() => {
	frames = [];
	vi.stubGlobal("requestAnimationFrame", (frame: FrameRequestCallback) => frames.push(frame));
	clearLoadedPages();
});

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
	document.body.innerHTML = "";
});

describe("a page's code", () => {
	it("is imported once the frame has painted its skeleton", async () => {
		painted(true);
		const loader = vi.fn(async () => page);

		const host = await open(loader);
		expect(loader).not.toHaveBeenCalled();
		expect(host.querySelector("[data-frame-skeleton]")).not.toBeNull();

		await paint();
		expect(loader).toHaveBeenCalledOnce();
		expect(host.querySelector("[data-page]")).not.toBeNull();
	});

	it("is imported at once in a hidden tab, which paints no frame", async () => {
		painted(true);
		vi.spyOn(document, "hidden", "get").mockReturnValue(true);
		const loader = vi.fn(async () => page);

		const host = await open(loader);
		expect(loader).toHaveBeenCalledOnce();
		expect(host.querySelector("[data-page]")).not.toBeNull();
	});

	it("is imported when the tab goes hidden before the frame paints", async () => {
		painted(true);
		const loader = vi.fn(async () => page);

		const host = await open(loader);
		expect(loader).not.toHaveBeenCalled();

		vi.spyOn(document, "hidden", "get").mockReturnValue(true);
		document.dispatchEvent(new Event("visibilitychange"));
		await settle();
		expect(loader).toHaveBeenCalledOnce();
		expect(host.querySelector("[data-page]")).not.toBeNull();
	});

	it("is imported at once before the document's first paint", async () => {
		painted(false);
		const loader = vi.fn(async () => page);

		const host = await open(loader);
		expect(loader).toHaveBeenCalledOnce();
		expect(host.querySelector("[data-page]")).not.toBeNull();
	});
});
