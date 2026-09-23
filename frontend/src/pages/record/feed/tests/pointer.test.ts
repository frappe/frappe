// `?activity=<key>`: read once as the record opens, it brings Activity forward over any `?tab=` and lands on the row.
// A scroll onto an Activity tab a script hid warns once.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, reactive, ref, shallowRef, type EffectScope } from "vue";
import { createRecordPage, type RecordPageController } from "@/recordPage/createRecordPage";
import { registerRecordPage, resetRegistry } from "@/recordPage/registry";
import { recordTabBuiltins } from "../../tabs/recordTabs";
import { useRecordTabs } from "../../tabs/useRecordTabs";
import { RecordFeeds } from "../recordFeeds";
import { fakeTimeline } from "./fakeTimeline";

let scope: EffectScope;

// The page's own reads answer empty: nothing here is about them.
const fetchMock = vi.fn(async () => new Response(JSON.stringify({ data: null })));

beforeEach(() => {
	vi.stubGlobal("fetch", fetchMock);
	resetRegistry();
	scope = effectScope();
	vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
	scope.stop();
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
});

/** One record page wired as `Record.vue` wires it, with a router that settles a tick later. */
function makePage(query: Record<string, string>) {
	const route = reactive({ query: { ...query } as Record<string, any>, hash: "" });
	const router = {
		replace: vi.fn(async (to: { query: Record<string, any> }) => {
			await Promise.resolve();
			route.query = to.query;
		}),
	} as any;
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

	async function open(docname = "CRM-DEAL-1") {
		const pointer = feeds.pointerOnOpen("CRM Deal", docname, route.query as any);
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
		feeds.showPointedTab(pointer);
		await controller.value.refresh();
		await settle();
		if (pointer) controller.value.page.activity.scrollTo(pointer);
		return pointer;
	}

	return { route, tabs, feeds, open };
}

async function settle() {
	for (let turn = 0; turn < 3; turn++) await nextTick();
}

describe("?activity=<key>", () => {
	it("opens Activity over a ?tab= naming another tab, and stays in the address", async () => {
		const { route, tabs, feeds, open } = makePage({ tab: "files", activity: "comment:c2" });
		const { handle, scrollToRow, paginate } = fakeTimeline([["comment:c3"], ["comment:c2"]]);
		feeds.attach(handle);

		await open();

		expect(tabs.shown.value).toBe("activity");
		expect(route.query).toEqual({ tab: "activity", activity: "comment:c2" });
		await vi.waitFor(() => expect(scrollToRow).toHaveBeenLastCalledWith("comment:c2"));
		expect(scrollToRow).toHaveLastReturnedWith(true);
		expect(paginate.fetchNextPage).toHaveBeenCalledTimes(1);
	});

	it("leaves ?tab= alone when there is no pointer", async () => {
		const { route, tabs, open } = makePage({ tab: "files" });

		expect(await open()).toBe("");
		expect(tabs.shown.value).toBe("files");
		expect(route.query).toEqual({ tab: "files" });
	});

	it("is read once: a reload of the same record does not move the reader again", async () => {
		const { feeds } = makePage({});
		const query = { activity: "comment:c2" };

		expect(feeds.pointerOnOpen("CRM Deal", "D-1", query)).toBe("comment:c2");
		expect(feeds.pointerOnOpen("CRM Deal", "D-1", query)).toBe("");
		expect(feeds.pointerOnOpen("CRM Deal", "D-2", query)).toBe("comment:c2");
	});

	it("lands on a new key on the same record as a cold load does", async () => {
		const { route, tabs, feeds, open } = makePage({ tab: "files" });
		const { handle, scrollToRow } = fakeTimeline([["comment:c3"], ["comment:c2"]]);
		feeds.attach(handle);
		await open();

		route.query = { tab: "files", activity: "comment:c2" };
		feeds.followPointer("CRM Deal", "CRM-DEAL-1", route.query as any);

		await vi.waitFor(() => expect(scrollToRow).toHaveLastReturnedWith(true));
		expect(scrollToRow).toHaveBeenLastCalledWith("comment:c2");
		expect(tabs.shown.value).toBe("activity");
		expect(route.query).toEqual({ tab: "activity", activity: "comment:c2" });
	});

	it("does nothing for the page's own ?tab= replace, the same key, or another record's", async () => {
		const { feeds, open } = makePage({ activity: "comment:c3" });
		const { handle, scrollToRow } = fakeTimeline([["comment:c3"]]);
		feeds.attach(handle);
		await open();
		await vi.waitFor(() => expect(scrollToRow).toHaveBeenCalledTimes(1));

		feeds.followPointer("CRM Deal", "CRM-DEAL-1", { tab: "files", activity: "comment:c3" });
		feeds.followPointer("CRM Deal", "CRM-DEAL-2", { activity: "comment:c9" });
		await settle();

		expect(scrollToRow).toHaveBeenCalledTimes(1);
	});
});

describe("page.activity.scrollTo onto a hidden Activity tab", () => {
	it("warns once, naming the hidden tab", async () => {
		registerRecordPage("CRM Deal", {
			onRefresh: (page) => {
				page.tabs.hide("activity");
				page.activity.scrollTo("comment:c1");
			},
		});
		const { open } = makePage({});

		await open();
		await settle();

		const warnings = vi.mocked(console.warn).mock.calls.map(([message]) => String(message));
		expect(warnings).toEqual([
			`[record-page] page.activity.scrollTo("comment:c1") — the Activity tab is hidden, so the reader was not moved.`,
		]);
	});
});
