// The record's one upload dialog: every request opens it over the tab shown, never moving to Files.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { DocInfo } from "../../panel/context";
import { recordTabBuiltins } from "../../tabs/recordTabs";
import { RecordFeeds, RecordFeedsKey } from "../recordFeeds";
import RecordUploadDialog from "../RecordUploadDialog.vue";

const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

function makeFeeds(docinfo: DocInfo) {
	return new RecordFeeds({
		docinfo: ref(docinfo),
		controller: () => null,
		showTab: async () => true,
		reloadParts: async () => {},
		whileOnRecord: () => () => true,
	});
}

async function mountPage(feeds: RecordFeeds) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const page = { doctype: "CRM Deal", docname: "D-1" };
	const app = createApp({
		render: () => [h("div", { "data-tab-body": "activity" }), h(RecordUploadDialog, { page })],
	});
	app.provide(RecordFeedsKey, feeds);
	app.mount(root);
	apps.push(app);
	await nextTick();
	return root;
}

function dialog() {
	return document.querySelector("[role='dialog']");
}

describe("the record's upload dialog", () => {
	it("opens from Attach a file while Activity is shown and Files was never visited", async () => {
		const feeds = makeFeeds({ permissions: { write: 1 } });
		const root = await mountPage(feeds);
		const create = recordTabBuiltins({ requestUpload: () => feeds.requestUpload() }).find(
			(tab) => tab.name === "files"
		)!.create!;
		const tabs = { active: "activity", activate: vi.fn() };

		create.run({ tabs } as any);

		await vi.waitFor(() => expect(dialog()).not.toBeNull());
		expect(tabs.activate).not.toHaveBeenCalled();
		expect(tabs.active).toBe("activity");
		expect(root.querySelector("[data-file-upload]")).toBeNull();
		expect(feeds.uploadRequested.value).toBe(false);
	});

	it("opens for a request made before it mounted, once", async () => {
		const feeds = makeFeeds({ permissions: { write: 1 } });
		feeds.requestUpload();

		await mountPage(feeds);

		await vi.waitFor(() => expect(dialog()).not.toBeNull());
		expect(feeds.uploadRequested.value).toBe(false);
	});

	it("takes a request without opening anything for a reader who may not write", async () => {
		const feeds = makeFeeds({ permissions: { read: 1 } });
		await mountPage(feeds);

		feeds.requestUpload();
		await nextTick();
		await nextTick();

		expect(dialog()).toBeNull();
		expect(feeds.uploadRequested.value).toBe(false);
	});
});
