// The feeds host: `scrollToActivity` pages older until the row is drawn, the eager read, and the files part.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import type { DocInfo } from "../../panel/context";
import { RecordFeeds, prefetchFeed } from "../recordFeeds";
import { fakeTimeline } from "./fakeTimeline";

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

	it("stops without paging when the row is loaded but folded into a run", async () => {
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

	it("does not move the reader when a script hid the Activity tab", async () => {
		const { feeds } = makeFeeds(null, async () => false);
		const { handle, scrollToRow } = fakeTimeline(PAGES);
		feeds.attach(handle);

		expect(await feeds.scrollToActivity("comment:c3")).toBe(false);
		expect(scrollToRow).not.toHaveBeenCalled();
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
});

describe("the eager read", () => {
	function activityReads() {
		return fetchMock.mock.calls
			.map(([url]) => new URL(String(url), "http://x"))
			.filter((url) => url.pathname.endsWith("/activity"));
	}

	it("starts the Activity read for an address with no tab", () => {
		prefetchFeed("CRM Deal", "EAGER-1", {});
		const [read] = activityReads();
		expect(read.pathname).toBe("/api/v2/document/CRM%20Deal/EAGER-1/activity");
		expect(read.searchParams.get("types")).toBeNull();
		expect(read.searchParams.get("limit")).toBe("50");
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
});

describe("the files part", () => {
	const OLD = { name: "F-1", file_name: "a.pdf", file_url: "/files/a.pdf", is_private: 0 as const, creation: "2026-09-01 10:00:00", owner: "ann@example.com" };
	const NEW = { ...OLD, name: "F-2", file_name: "b.pdf", creation: "2026-09-05 10:00:00" };

	it("hands the rows oldest first", () => {
		const { feeds } = makeFeeds({ attachments: [NEW, OLD] });
		expect(feeds.pageHost.fileRows().map((file) => file.name)).toEqual(["F-1", "F-2"]);
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
