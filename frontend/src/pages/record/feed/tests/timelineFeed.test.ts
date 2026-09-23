// A feed tab over the real timeline: the feed scrolls, so the reader tabs into it once, and an
// email row offers Reply and Reply all while the email writer is listed.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, shallowRef } from "vue";

const feed = vi.hoisted(() => ({ rows: [] as unknown[] }));

vi.mock("@framework/ui/ActivityTimeline", async (importOriginal) => {
	const vue = await import("vue");
	return {
		...((await importOriginal()) as object),
		useActivityTimeline: () => ({
			activities: vue.ref(feed.rows),
			loading: vue.ref(false),
			error: vue.ref(null),
			reload: async () => {},
			paginate: vue.reactive({ hasNextPage: false, isFetchingNextPage: false, fetchNextPage: async () => {} }),
		}),
	};
});

import TimelineFeed from "../TimelineFeed.vue";
import { RecordFeedsKey } from "../recordFeeds";

const ScriptRow = defineComponent({ setup: () => () => h("span", "a script row") });
const SCRIPT_ROW = {
	type: "script",
	key: "call:1",
	timestamp: "2026-09-20 10:00:00",
	data: { component: ScriptRow },
};

function emailRow(name: string, pending = false) {
	return {
		type: "email",
		key: `email:${name}`,
		timestamp: "2026-09-20 11:00:00",
		author: { fullname: "Ann" },
		pending,
		data: { name, sender: "ann@example.com", to: "bo@example.com", subject: "Hello", content: "<p>Hi</p>" },
	};
}

const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mountFeed(rows: unknown[], writers: string[] = ["comment"]) {
	feed.rows = rows;
	const root = document.createElement("div");
	document.body.appendChild(root);
	const open = vi.fn();
	const page = { doctype: "CRM Deal", docname: "D-1", composer: { open } };
	const controller = { composer: { visible: () => writers.map((name) => ({ name, label: name })) } };
	const app = createApp(defineComponent({ setup: () => () => h(TimelineFeed, { page: page as any }) }));
	const feeds = { controller: () => controller, composerBand: shallowRef(0) };
	app.provide(RecordFeedsKey, feeds as any);
	app.mount(root);
	apps.push(app);
	await nextTick();
	return { root, open };
}

const replies = (root: HTMLElement) => root.querySelectorAll("[data-email-reply], [data-email-reply-all]");

describe("a timeline feed tab", () => {
	it("has one tab stop, the feed's own scroller", async () => {
		const { root } = await mountFeed([SCRIPT_ROW]);

		expect(root.textContent).toContain("a script row");
		const stops = root.querySelectorAll('[tabindex="0"]');
		expect(stops).toHaveLength(1);
		expect(stops[0].hasAttribute("data-reka-scroll-area-viewport")).toBe(true);
	});
});

describe("an email row's replies", () => {
	it("are absent while the email writer is not listed", async () => {
		const { root } = await mountFeed([emailRow("COMM-1")]);
		expect(root.textContent).toContain("bo@example.com");
		expect(replies(root)).toHaveLength(0);
	});

	it("open the email writer replying to the row, and to everyone on it", async () => {
		const { root, open } = await mountFeed([emailRow("COMM-1")], ["comment", "email"]);
		expect(root.textContent).toContain("bo@example.com");
		root.querySelector<HTMLElement>("[data-email-reply]")!.click();
		expect(open).toHaveBeenLastCalledWith("email", { draft: { replyTo: "email:COMM-1" } });
		root.querySelector<HTMLElement>("[data-email-reply-all]")!.click();
		expect(open).toHaveBeenLastCalledWith("email", {
			draft: { replyTo: "email:COMM-1", replyAll: true },
		});
	});

	it("are absent on a row still sending", async () => {
		const { root } = await mountFeed([emailRow("COMM-2", true)], ["email"]);
		expect(root.textContent).toContain("bo@example.com");
		expect(replies(root)).toHaveLength(0);
	});
});
