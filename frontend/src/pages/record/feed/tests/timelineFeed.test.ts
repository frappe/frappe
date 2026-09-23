// A feed tab over the real timeline: the feed scrolls, so the reader tabs into it once.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";

vi.mock("@framework/ui/ActivityTimeline", async (importOriginal) => {
	const vue = await import("vue");
	const Row = vue.defineComponent({ setup: () => () => vue.h("span", "a script row") });
	const row = { type: "script", key: "call:1", timestamp: "2026-09-20 10:00:00", data: { component: Row } };
	return {
		...((await importOriginal()) as object),
		useActivityTimeline: () => ({
			activities: vue.ref([row]),
			loading: vue.ref(false),
			error: vue.ref(null),
			reload: async () => {},
			paginate: vue.reactive({ hasNextPage: false, isFetchingNextPage: false, fetchNextPage: async () => {} }),
		}),
	};
});

import TimelineFeed from "../TimelineFeed.vue";

const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mountFeed() {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const page = { doctype: "CRM Deal", docname: "D-1" };
	const app = createApp(defineComponent({ setup: () => () => h(TimelineFeed, { page: page as any }) }));
	app.mount(root);
	apps.push(app);
	await nextTick();
	return root;
}

describe("a timeline feed tab", () => {
	it("has one tab stop, the feed's own scroller", async () => {
		const root = await mountFeed();

		expect(root.textContent).toContain("a script row");
		const stops = root.querySelectorAll('[tabindex="0"]');
		expect(stops).toHaveLength(1);
		expect(stops[0].hasAttribute("data-reka-scroll-area-viewport")).toBe(true);
	});
});
