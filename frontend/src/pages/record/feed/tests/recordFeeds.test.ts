// The feeds host: `scrollToActivity` pages older until the row is drawn, the eager read, and the files part.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import type { RecordPageController } from "@/recordPage";
import type { DocInfo } from "../../panel/context";
import { endActivityPrefetch } from "@framework/ui/ActivityTimeline";
import { RecordFeeds, endPrefetchFeed, prefetchFeed, withFeedRead } from "../recordFeeds";
import { fakeTimeline } from "./fakeTimeline";

vi.mock("@framework/ui/ActivityTimeline", async (importOriginal) => {
	const actual = (await importOriginal()) as Record<string, (...args: unknown[]) => unknown>;
	return { ...actual, endActivityPrefetch: vi.fn(actual.endActivityPrefetch) };
});

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
	vi.stubGlobal("fetch", fetchMock);
	fetchMock.mockReset();
	fetchMock.mockImplementation(async () => respond({ activities: [], next: null }));
});
afterEach(() => vi.unstubAllGlobals());

function respond(data: unknown) {
	return new Response(JSON.stringify({ data }), { status: 200 });
}

function makeFeeds(docinfo: DocInfo | null = null, showTab = async () => true) {
	let current = true;
	const feeds = new RecordFeeds({
		docinfo: ref(docinfo),
		controller: () => null,
		showTab: vi.fn(showTab),
		reloadParts: vi.fn(async () => {}),
		whileOnRecord: () => () => current,
	});
	return { feeds, moveOn: () => (current = false) };
}

const PAGES = [["comment:c3"], ["comment:c2"], ["comment:c1"]];

describe("scrollToActivity", () => {
	it("opens Activity and pages older until the row is drawn", async () => {
		const { feeds } = makeFeeds();
		const { handle, paginate, scrollToRow } = fakeTimeline(PAGES);
		feeds.attach(handle);

		expect(await feeds.pageHost.scrollToActivity("comment:c1")).toBe(true);
		expect(paginate.fetchNextPage).toHaveBeenCalledTimes(2);
		expect(scrollToRow).toHaveBeenLastCalledWith("comment:c1");
	});

	it("answers false once the list ends without the row", async () => {
		const { feeds } = makeFeeds();
		const { handle, paginate } = fakeTimeline(PAGES);
		feeds.attach(handle);

		expect(await feeds.scrollToActivity("comment:gone")).toBe(false);
		expect(paginate.fetchNextPage).toHaveBeenCalledTimes(2);
	});

	it("stops at a failed read, which leaves hasNextPage true", async () => {
		const { feeds } = makeFeeds();
		const { handle, paginate } = fakeTimeline(PAGES, { failAt: 1 });
		feeds.attach(handle);

		expect(await feeds.scrollToActivity("comment:c1")).toBe(false);
		expect(paginate.fetchNextPage).toHaveBeenCalledTimes(1);
		expect(paginate.hasNextPage).toBe(true);
	});

	it("stops without paging when the row is loaded but netted out of a run", async () => {
		const { feeds } = makeFeeds();
		const { handle, paginate } = fakeTimeline(PAGES, { folded: ["comment:c3"] });
		feeds.attach(handle);

		expect(await feeds.scrollToActivity("comment:c3")).toBe(false);
		expect(paginate.fetchNextPage).not.toHaveBeenCalled();
	});

	it("waits for the body to mount and its first page to land", async () => {
		const { feeds } = makeFeeds();
		const { handle, loading, scrollToRow } = fakeTimeline(PAGES);
		loading.value = true;

		const moved = feeds.scrollToActivity("comment:c3");
		await nextTick();
		feeds.attach(handle);
		await nextTick();
		expect(scrollToRow).not.toHaveBeenCalled();
		loading.value = false;

		expect(await moved).toBe(true);
	});

	it("does not move the reader when a script hid the Activity tab, and leaves the warning to the tab strip", async () => {
		const { feeds } = makeFeeds(null, async () => false);
		const { handle, scrollToRow } = fakeTimeline(PAGES);
		feeds.attach(handle);

		expect(await feeds.scrollToActivity("comment:c3")).toBe(null);
		expect(scrollToRow).not.toHaveBeenCalled();
	});

	it("answers null, with its own warning naming the key, when the Activity body never draws", async () => {
		vi.useFakeTimers();
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		try {
			const { feeds } = makeFeeds();
			const moved = feeds.scrollToActivity("comment:c1");
			await vi.advanceTimersByTimeAsync(2000);

			expect(await moved).toBe(null);
			expect(warn).toHaveBeenCalledTimes(1);
			expect(warn.mock.calls[0][0]).toContain('page.activity.scrollTo("comment:c1")');
			expect(warn.mock.calls[0][0]).toContain("drew no activity feed");
		} finally {
			warn.mockRestore();
			vi.useRealTimers();
		}
	});

	it("gives up once the page has moved to another record", async () => {
		const { feeds, moveOn } = makeFeeds();
		const { handle, paginate } = fakeTimeline(PAGES);
		feeds.attach(handle);
		moveOn();

		expect(await feeds.scrollToActivity("comment:c1")).toBe(false);
		expect(paginate.fetchNextPage).not.toHaveBeenCalled();
	});
});

describe("the Activity rows the host hands page.activity", () => {
	it("are the mounted body's rows, and none once it lets go", async () => {
		const { feeds } = makeFeeds();
		const release = feeds.attach(fakeTimeline(PAGES).handle);
		expect(feeds.pageHost.activityRows().map((one) => one.key)).toEqual(["comment:c3"]);

		release();
		expect(feeds.pageHost.activityRows()).toEqual([]);
	});

	it("are the eager read's once its first page is in, before the body mounts", async () => {
		const feeds = onRecord("PRE-1");
		fetchMock.mockImplementation(async () => respond({ activities: [comment("comment:c1")], next: null }));

		const read = prefetchFeed("CRM Deal", "PRE-1", { tab: "activity" });
		expect(feeds.pageHost.activityRows()).toEqual([]);
		await read;

		expect(feeds.pageHost.activityRows().map((one) => one.key)).toEqual(["comment:c1"]);
	});

	it("are read again by a reload before the body mounts", async () => {
		const feeds = onRecord("PRE-2");
		await prefetchFeed("CRM Deal", "PRE-2", { tab: "activity" });
		fetchMock.mockImplementation(async () => respond({ activities: [comment("comment:c2")], next: null }));

		await feeds.pageHost.reloadActivity();

		expect(feeds.pageHost.activityRows().map((one) => one.key)).toEqual(["comment:c2"]);
	});

	function onRecord(docname: string) {
		const page = { doctype: "CRM Deal", docname };
		const controller = { page, activity: { shownTypes: () => null } } as unknown as RecordPageController;
		return new RecordFeeds({
			docinfo: ref(null),
			controller: () => controller,
			showTab: async () => true,
			reloadParts: async () => {},
			whileOnRecord: () => () => true,
		});
	}

	function comment(key: string) {
		return { type: "comment", key, timestamp: "2026-09-20 10:00:00", author: { email: "a@x.com", fullname: "A" }, data: {} };
	}
});

describe("the eager read", () => {
	function activityReads() {
		return fetchMock.mock.calls
			.map(([url]) => new URL(String(url), "http://x"))
			.filter((url) => url.pathname.endsWith("/activity"));
	}

	it("starts the Activity read for `?tab=activity`", () => {
		prefetchFeed("CRM Deal", "EAGER-1", { tab: "activity" });
		const [read] = activityReads();
		expect(read.pathname).toBe("/api/v2/document/CRM%20Deal/EAGER-1/activity");
		expect(read.searchParams.get("types")).toBeNull();
		expect(read.searchParams.get("limit")).toBeNull();
	});

	it("starts the Activity read for a pointer alone", () => {
		prefetchFeed("CRM Deal", "EAGER-10", { activity: "comment:c1" });
		const [read] = activityReads();
		expect(read.pathname).toBe("/api/v2/document/CRM%20Deal/EAGER-10/activity");
		expect(read.searchParams.get("types")).toBeNull();
	});

	it("ends both reads' first-paint pass together", () => {
		endPrefetchFeed("CRM Deal", "EAGER-5");
		expect(vi.mocked(endActivityPrefetch).mock.calls).toEqual([
			["CRM Deal", "EAGER-5"],
			["CRM Deal", "EAGER-5", ["email"]],
		]);
	});

	it("ends the first-paint pass once the open is over, and not before", async () => {
		vi.mocked(endActivityPrefetch).mockClear();
		let endedDuringOpen = true;

		await withFeedRead("CRM Deal", "EAGER-6", { tab: "activity" }, async (feedRead) => {
			await feedRead;
			endedDuringOpen = vi.mocked(endActivityPrefetch).mock.calls.length > 0;
		});

		expect(endedDuringOpen).toBe(false);
		expect(vi.mocked(endActivityPrefetch)).toHaveBeenCalledWith("CRM Deal", "EAGER-6");
	});

	it("ends it for an open a newer load cut short, or one that threw", async () => {
		vi.mocked(endActivityPrefetch).mockClear();

		await withFeedRead("CRM Deal", "EAGER-7", {}, async () => {});
		const failed = withFeedRead("CRM Deal", "EAGER-8", {}, async () => {
			throw new Error("record gone");
		});

		await expect(failed).rejects.toThrow("record gone");
		const ended = vi.mocked(endActivityPrefetch).mock.calls.map(([, docname]) => docname);
		expect(ended).toEqual(["EAGER-7", "EAGER-7", "EAGER-8", "EAGER-8"]);
	});

	it("starts the email read for the Emails tab", () => {
		prefetchFeed("CRM Deal", "EAGER-2", { tab: "emails" });
		expect(JSON.parse(activityReads()[0].searchParams.get("types")!)).toEqual(["email"]);
	});

	it("reads nothing for another tab, unless a pointer names Activity", () => {
		prefetchFeed("CRM Deal", "EAGER-3", { tab: "files" });
		expect(activityReads()).toHaveLength(0);

		prefetchFeed("CRM Deal", "EAGER-4", { tab: "files", activity: "comment:c1" });
		expect(activityReads()).toHaveLength(1);
	});

	it("reads nothing for an address with no tab, so the open waits on no read", async () => {
		fetchMock.mockImplementation(() => new Promise<Response>(() => {}));

		await withFeedRead("CRM Deal", "EAGER-9", {}, async (feedRead) => {
			await feedRead;
		});

		expect(activityReads()).toHaveLength(0);
	});
});

describe("the files part", () => {
	const OLD = { name: "F-1", file_name: "a.pdf", file_url: "/files/a.pdf", is_private: 0 as const, creation: "2026-09-01 10:00:00", owner: "ann@example.com" };
	const NEW = { ...OLD, name: "F-2", file_name: "b.pdf", creation: "2026-09-05 10:00:00" };

	it("hands the rows oldest first", () => {
		const { feeds } = makeFeeds({ attachments: [NEW, OLD] });
		expect(feeds.pageHost.fileRows().map((file) => file.name)).toEqual(["F-1", "F-2"]);
	});

	it("orders rows in the same millisecond by the time's text, then the name by code unit", () => {
		const late = { ...OLD, name: "file-a", creation: "2026-09-01 10:00:00.500900" };
		const early = { ...OLD, name: "file-z", creation: "2026-09-01 10:00:00.500100" };
		const tie = { ...OLD, name: "file-B", creation: "2026-09-01 10:00:00.500900" };
		const { feeds } = makeFeeds({ attachments: [late, early, tie] });
		expect(feeds.pageHost.fileRows().map((file) => file.name)).toEqual(["file-z", "file-B", "file-a"]);
	});

	it("replaces the part from the delete's answer", async () => {
		const { feeds } = makeFeeds({ attachments: [OLD, NEW], users: {} });
		fetchMock.mockImplementation(async () =>
			respond({ attachments: [OLD], users: { "ann@example.com": { full_name: "Ann" } } })
		);

		await feeds.removeFile("CRM Deal", "D-1", "F-2");

		const [url, init] = fetchMock.mock.calls[0];
		expect(init?.method).toBe("DELETE");
		expect(String(url)).toContain("/document/CRM%20Deal/D-1/attachments/F-2");
		expect(feeds.docinfo()?.attachments).toEqual([OLD]);
		expect(feeds.docinfo()?.users).toEqual({ "ann@example.com": { full_name: "Ann" } });
	});

	it("drops an answer that outlived its record", async () => {
		const { feeds, moveOn } = makeFeeds({ attachments: [OLD, NEW] });
		fetchMock.mockImplementation(async () => {
			moveOn();
			return respond({ attachments: [] });
		});

		await feeds.removeFile("CRM Deal", "D-1", "F-2");

		expect(feeds.docinfo()?.attachments).toEqual([OLD, NEW]);
	});
});
