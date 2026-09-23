// The three built-in tab bodies: Activity with a script's rows, Emails on its own read, and Files.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type Component } from "vue";

const timeline = vi.hoisted(() => ({
	reads: [] as { docname: string; types: unknown }[],
	rows: null as any,
}));

vi.mock("@framework/ui/ActivityTimeline", async (importOriginal) => {
	const vue = await import("vue");
	timeline.rows = vue.ref([]);
	return {
		...((await importOriginal()) as object),
		useActivityTimeline: (_doctype: string, docname: string, types?: unknown) => {
			timeline.reads.push({ docname, types });
			return {
				activities: vue.computed(() => timeline.rows.value),
				loading: vue.ref(false),
				error: vue.ref(null),
				reload: async () => {},
				paginate: vue.reactive({ hasNextPage: false, isFetchingNextPage: false, fetchNextPage: async () => {} }),
			};
		},
		// Draws each row through its type's slot, as the real timeline does for a custom type.
		ActivityTimeline: vue.defineComponent({
			props: { activities: Array, loading: Boolean, paginate: Object },
			setup(props: any, { slots, expose }) {
				expose({ scrollToRow: () => true });
				return () =>
					props.activities.length
						? vue.h(
								"ol",
								props.activities.map((row: any) =>
									vue.h("li", { "data-row": row.key }, slots[`item-${row.type}`]?.({ activity: row }) ?? row.key)
								)
							)
						: vue.h("div", slots.empty?.() ?? "No activity yet");
			},
		}),
	};
});

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...((await importOriginal()) as object),
	attachFile: vi.fn(),
}));

import { attachFile } from "@framework/ui/api";
import type { FeedItem } from "@/recordPage";
import { createRecordPage, type RecordPageController } from "@/recordPage/createRecordPage";
import type { DocInfo } from "../../panel/context";
import { recordTabBuiltins } from "../../tabs/recordTabs";
import { RecordFeeds, RecordFeedsKey } from "../recordFeeds";

const CallRow = defineComponent({
	props: { id: Number, page: Object },
	setup: (props) => () => h("span", { "data-call": "" }, `call ${props.id} on ${props.page?.docname}`),
});

const apps: ReturnType<typeof createApp>[] = [];
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
	vi.stubGlobal("fetch", fetchMock);
	timeline.reads.length = 0;
	timeline.rows.value = [];
});
afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	vi.unstubAllGlobals();
});

const OLD = { name: "F-1", file_name: "brief.pdf", file_url: "/files/brief.pdf", is_private: 1 as const, creation: "2026-09-01 10:00:00", owner: "ann@example.com" };
const NEW = { ...OLD, name: "F-2", file_name: "photo.png", is_private: 0 as const, creation: "2026-09-05 10:00:00" };

function setup(docinfo: DocInfo | null = null, own: { activity?: FeedItem[]; files?: FeedItem[] } = {}) {
	const shownTypes = ref<string[] | null>(null);
	const page = { doctype: "CRM Deal", docname: "D-1", dialog: { confirm: vi.fn(async () => true) } } as any;
	const controller = {
		page,
		activity: { visible: () => own.activity ?? [], shownTypes: () => shownTypes.value },
		files: { visible: () => own.files ?? [] },
	} as any;
	const feeds = new RecordFeeds({
		docinfo: ref(docinfo),
		controller: () => controller,
		showTab: async () => true,
		reloadParts: async () => {},
		whileOnRecord: () => () => true,
	});
	return { feeds, page, shownTypes };
}

async function mountTab(name: string, feeds: RecordFeeds, page: any) {
	const tab = recordTabBuiltins().find((one) => one.name === name)!;
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({ render: () => h(tab.component as Component, { ...tab.props, page }) });
	app.provide(RecordFeedsKey, feeds);
	app.mount(root);
	apps.push(app);
	await nextTick();
	return { root, app };
}

function keys(root: HTMLElement) {
	return [...root.querySelectorAll("[data-row]")].map((row) => row.getAttribute("data-row"));
}

describe("the Activity tab", () => {
	it("draws the server's rows with a script's row in time order", async () => {
		timeline.rows.value = [
			{ type: "comment", key: "comment:a", timestamp: "2026-09-20 10:00:00", data: {} },
			{ type: "comment", key: "comment:b", timestamp: "2026-09-20 12:00:00", data: {} },
		];
		const call = { name: "call:17", timestamp: "2026-09-20 11:00:00", component: CallRow, props: { id: 17 } };
		const { feeds, page } = setup(null, { activity: [call] });

		const { root } = await mountTab("activity", feeds, page);

		expect(keys(root)).toEqual(["comment:a", "call:17", "comment:b"]);
		expect(root.querySelector("[data-call]")!.textContent).toBe("call 17 on D-1");
	});

	it("reads every type, then the types a script chose, and answers the host while mounted", async () => {
		timeline.rows.value = [{ type: "comment", key: "comment:a", timestamp: "2026-09-20 10:00:00", data: {} }];
		const { feeds, page, shownTypes } = setup();

		const { app } = await mountTab("activity", feeds, page);
		shownTypes.value = ["comment"];
		await nextTick();

		expect(timeline.reads).toEqual([
			{ docname: "D-1", types: undefined },
			{ docname: "D-1", types: ["comment"] },
		]);
		expect(feeds.pageHost.activityRows().map((row) => row.key)).toEqual(["comment:a"]);
		app.unmount();
		apps.length = 0;
		expect(feeds.pageHost.activityRows()).toEqual([]);
	});
});

describe("the Emails tab", () => {
	it("reads its own email-only feed and is not the one the host answers from", async () => {
		timeline.rows.value = [{ type: "email", key: "email:e1", timestamp: "2026-09-20 10:00:00", data: {} }];
		const { feeds, page } = setup();

		const { root } = await mountTab("emails", feeds, page);

		expect(timeline.reads).toEqual([{ docname: "D-1", types: ["email"] }]);
		expect(keys(root)).toEqual(["email:e1"]);
		expect(feeds.pageHost.activityRows()).toEqual([]);
	});

	it("says there are no emails when there are none", async () => {
		const { feeds, page } = setup();

		const { root } = await mountTab("emails", feeds, page);

		expect(root.textContent).toContain("No emails yet");
	});
});

describe("the Files tab", () => {
	function fileNames(root: HTMLElement) {
		return [...root.querySelectorAll("[data-file-row]")].map((row) => row.getAttribute("data-file-row"));
	}

	it("lists the attachments part oldest first, with a script's row among them", async () => {
		const note = { name: "note:1", timestamp: "2026-09-03 10:00:00", component: CallRow, props: { id: 1 } };
		const { feeds, page } = setup({ attachments: [NEW, OLD], permissions: { write: 1 } }, { files: [note] });

		const { root } = await mountTab("files", feeds, page);

		expect(fileNames(root)).toEqual(["F-1", "F-2"]);
		const drawn = root.querySelector("[data-file-row='F-1']")!.parentElement!.textContent!;
		expect(drawn.indexOf("brief.pdf")).toBeLessThan(drawn.indexOf("call 1"));
		expect(drawn.indexOf("call 1")).toBeLessThan(drawn.indexOf("photo.png"));
	});

	it("draws no upload button and no delete control for a reader who may not write", async () => {
		const { feeds, page } = setup({ attachments: [OLD], permissions: { read: 1 } });

		const { root } = await mountTab("files", feeds, page);

		expect(root.querySelector("[data-file-remove]")).toBeNull();
		expect(root.querySelector("[data-file-upload]")).toBeNull();
	});

	it("draws the upload button for a reader who may write", async () => {
		const { feeds, page } = setup({ attachments: [OLD], permissions: { write: 1 } });

		const { root } = await mountTab("files", feeds, page);

		expect(root.querySelector("[data-file-upload]")).not.toBeNull();
	});

	it("deletes a file after the reader confirms, and draws the part the server answers with", async () => {
		const { feeds, page } = setup({ attachments: [OLD, NEW], permissions: { write: 1 } });
		fetchMock.mockImplementation(async () => new Response(JSON.stringify({ data: { attachments: [NEW] } })));

		const { root } = await mountTab("files", feeds, page);
		root.querySelector<HTMLElement>("[data-file-row='F-1'] [data-file-remove]")!.click();
		await vi.waitFor(() => expect(fileNames(root)).toEqual(["F-2"]));

		expect(page.dialog.confirm).toHaveBeenCalledTimes(1);
		expect(fetchMock.mock.calls[0][1]?.method).toBe("DELETE");
	});

	it("gives the `+` menu an Attach a file only with an upload to ask for", () => {
		expect(recordTabBuiltins().find((tab) => tab.name === "files")!.create).toBeUndefined();
		const requestUpload = vi.fn();
		const create = recordTabBuiltins({ requestUpload }).find((tab) => tab.name === "files")!.create!;
		expect(create).toMatchObject({ label: "Attach a file", icon: "lucide-paperclip" });
		const page = { tabs: { activate: vi.fn() } } as any;
		create.run(page);
		expect(page.tabs.activate).toHaveBeenCalledWith("files");
		expect(requestUpload).toHaveBeenCalledTimes(1);
	});

	it("opens the upload dialog for a request made before the tab mounted, once", async () => {
		const { feeds, page } = setup({ attachments: [OLD], permissions: { write: 1 } });
		feeds.requestUpload();

		await mountTab("files", feeds, page);

		await vi.waitFor(() => expect(document.querySelector("[role='dialog']")).not.toBeNull());
		expect(feeds.uploadRequested.value).toBe(false);
	});

	it("opens the upload dialog for a request made while the tab is mounted", async () => {
		const { feeds, page } = setup({ attachments: [OLD], permissions: { write: 1 } });
		await mountTab("files", feeds, page);
		expect(document.querySelector("[role='dialog']")).toBeNull();

		feeds.requestUpload();

		await vi.waitFor(() => expect(document.querySelector("[role='dialog']")).not.toBeNull());
	});

	it("takes a request without opening anything for a reader who may not write", async () => {
		const { feeds, page } = setup({ attachments: [OLD], permissions: { read: 1 } });
		feeds.requestUpload();

		await mountTab("files", feeds, page);
		await nextTick();

		expect(document.querySelector("[role='dialog']")).toBeNull();
		expect(feeds.uploadRequested.value).toBe(false);
	});

	it("uploads onto the record and keeps the part the attach route answers with", async () => {
		const { feeds } = setup({ attachments: [OLD] });
		vi.mocked(attachFile).mockResolvedValue({ data: { attachments: [OLD, NEW], file: "F-2" } } as any);
		const upload = feeds.uploadTransport("CRM Deal", "D-1");

		const file = new File(["x"], "photo.png");
		const signal = new AbortController().signal;
		const result = await upload(file, { isPrivate: true }, { signal, onProgress: () => {} });

		expect(result).toEqual({ file_url: NEW.file_url, name: "F-2" });
		expect(vi.mocked(attachFile).mock.calls[0].slice(0, 4)).toEqual([
			"CRM Deal",
			"D-1",
			file,
			{ is_private: 1, folder: "Home/Attachments", optimize: undefined, max_width: undefined, max_height: undefined },
		]);
		expect(feeds.pageHost.fileRows().map((row) => row.name)).toEqual(["F-1", "F-2"]);
	});
});

describe("the order a script reads", () => {
	/** A real page over the feeds host, so `items` comes from the engine, not from the test. */
	function realPage(docinfo: DocInfo | null) {
		let controller: RecordPageController | null = null;
		const feeds = new RecordFeeds({
			docinfo: ref(docinfo),
			controller: () => controller,
			showTab: async () => true,
			reloadParts: async () => {},
			whileOnRecord: () => () => true,
		});
		controller = createRecordPage({
			doctype: "CRM Deal",
			docname: "D-1",
			doc: ref({}),
			saved: ref({}),
			meta: ref(null),
			perms: () => ({}),
			isDirty: () => false,
			activeTab: () => "activity",
			activateTab: () => {},
			...feeds.pageHost,
			save: async () => {},
			reload: async () => {},
			router: {} as any,
		});
		return { feeds, page: controller.page };
	}

	it("is the order the Activity tab draws, for rows in the same millisecond", async () => {
		// As the store holds them: the time's text, then the key.
		timeline.rows.value = [
			{ type: "comment", key: "comment:b", timestamp: "2026-09-20 10:00:00.123400", data: {} },
			{ type: "comment", key: "comment:a", timestamp: "2026-09-20 10:00:00.123900", data: {} },
		];
		const { feeds, page } = realPage(null);
		page.activity.add({ name: "call:1", timestamp: "2026-09-20T10:00:00.123500", component: CallRow });

		const { root } = await mountTab("activity", feeds, page);

		expect(keys(root)).toEqual(["comment:b", "call:1", "comment:a"]);
		expect(page.activity.items.map((item) => item.name)).toEqual(keys(root));
	});

	it("is the order the Files tab draws, for rows in the same millisecond", async () => {
		const at = "2026-09-01 10:00:00.500000";
		const attachments = [
			{ ...OLD, name: "file-a", creation: at },
			{ ...OLD, name: "file-B", creation: at },
		];
		const { feeds, page } = realPage({ attachments });
		page.files.add({ name: "file-C", timestamp: at, component: CallRow, props: { id: 3 } });

		const { root } = await mountTab("files", feeds, page);

		const drawn = [...root.querySelectorAll("[data-file-row], [data-call]")].map(
			(row) => row.getAttribute("data-file-row") ?? "file-C"
		);
		expect(drawn).toEqual(["file-B", "file-C", "file-a"]);
		expect(page.files.items.map((item) => item.name)).toEqual(drawn);
	});
});
