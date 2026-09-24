// A script that moves Activity first: the plain load starts no early read, and the body reads on mount.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, effectScope, h, nextTick, reactive, ref, shallowRef, type EffectScope } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
	...((await importOriginal()) as object),
	Tabs: defineComponent({
		props: { modelValue: String, tabs: Array },
		setup: (props) => () =>
			h(
				"nav",
				(props.tabs as { value: string }[]).map((tab) => h("button", { "data-tab": tab.value }))
			),
	}),
}));

import { createRecordPage, type RecordPageController } from "@/recordPage/createRecordPage";
import { registerRecordPage, resetRegistry } from "@/recordPage/registry";
import RecordTabs from "../../tabs/RecordTabs.vue";
import { recordTabBuiltins } from "../../tabs/recordTabs";
import { useRecordTabs } from "../../tabs/useRecordTabs";
import { RecordFeeds, RecordFeedsKey, prefetchFeed } from "../recordFeeds";

const fetchMock = vi.fn<typeof fetch>();
const apps: ReturnType<typeof createApp>[] = [];
let scope: EffectScope;
let answer: (rows: unknown[]) => void;

beforeEach(() => {
	resetRegistry();
	scope = effectScope();
	vi.stubGlobal("fetch", fetchMock);
	fetchMock.mockReset();
	fetchMock.mockImplementation(async (url) => {
		if (!String(url).includes("/activity")) return respond(null);
		return new Promise<Response>((resolve) => {
			answer = (activities) => resolve(respond({ activities, next: null }));
		});
	});
});
afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	scope.stop();
	vi.unstubAllGlobals();
});

function respond(data: unknown) {
	return new Response(JSON.stringify({ data }), { status: 200 });
}

function activityReads() {
	return fetchMock.mock.calls.filter(([url]) => String(url).includes("/activity"));
}

async function settle() {
	for (let turn = 0; turn < 3; turn++) await nextTick();
}

/** One record page wired as `Record.vue` wires it, on a plain address, drawn through the real strip. */
async function openPlain(docname: string) {
	const route = reactive({ query: {} as Record<string, any>, hash: "" });
	const router = { replace: vi.fn(async () => {}) } as any;
	const controller = shallowRef<RecordPageController | null>(null);
	const tabs = scope.run(() =>
		useRecordTabs({ route: route as any, router, controller: () => controller.value, formTab: () => "" })
	)!;
	const feeds = new RecordFeeds({
		docinfo: ref(null),
		controller: () => controller.value,
		showTab: (name, what) => tabs.host.show(name, what),
		reloadParts: async () => {},
		whileOnRecord: () => () => true,
	});
	await prefetchFeed("CRM Deal", docname, route.query);
	const early = activityReads().length;

	controller.value = createRecordPage({
		doctype: "CRM Deal",
		docname,
		doc: ref({}),
		saved: ref({}),
		meta: ref(null),
		perms: () => ({}),
		isDirty: () => false,
		...tabs.pageHost,
		...feeds.pageHost,
		save: async () => {},
		reload: async () => {},
		router,
	});
	controller.value.tabs.provideBuiltins(recordTabBuiltins);
	await controller.value.refresh();

	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({
		render: () =>
			h(RecordTabs, {
				tabs: tabs.entries.value,
				active: tabs.shown.value,
				ready: controller.value!.ready.value,
				page: controller.value!.page,
			}),
	});
	app.provide(RecordFeedsKey, feeds);
	app.mount(root);
	apps.push(app);
	await settle();
	return { root, tabs, early };
}

describe("Activity moved first by a script", () => {
	it("starts no early read, then reads on mount: a skeleton, then the rows", async () => {
		registerRecordPage("CRM Deal", { onRefresh: (api) => api.tabs.order(["activity", "emails"]) });

		const { root, tabs, early } = await openPlain("FIRST-1");

		expect(early).toBe(0);
		expect(tabs.entries.value.map((entry) => entry.item.name)).toEqual(["activity", "emails", "details", "files"]);
		expect(tabs.shown.value).toBe("activity");
		expect(activityReads()).toHaveLength(1);
		const body = root.querySelector('[data-record-tab="activity"]')!;
		expect(body.querySelectorAll(".activity-timeline .fui-skeleton").length).toBeGreaterThan(0);
		expect(body.querySelectorAll(".activity")).toHaveLength(0);

		answer([comment("comment:c1")]);
		await vi.waitFor(() => expect(body.querySelectorAll(".activity")).toHaveLength(1));
		expect(body.querySelector(".activity")!.id).toBe("comment:c1");
	});

	it("opens Details with no feed read when no script moves Activity", async () => {
		const { root, tabs, early } = await openPlain("FIRST-2");

		expect(early).toBe(0);
		expect(tabs.shown.value).toBe("details");
		expect(activityReads()).toHaveLength(0);
		expect(root.querySelector('[data-record-tab="activity"]')).toBeNull();
	});
});

function comment(key: string) {
	return {
		type: "comment",
		key,
		timestamp: "2026-09-20 10:00:00",
		author: { email: "a@x.com", fullname: "A" },
		data: { content: "<p>Hello</p>" },
	};
}
