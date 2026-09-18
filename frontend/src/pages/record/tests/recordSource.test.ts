// The page's three server calls: which route each takes, which parts it asks for, and what it hands back.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadParts, loadRecord, saveRecord } from "../recordSource";

const fetchMock = vi.fn<typeof fetch>();

function respond(body: unknown, status = 200) {
	fetchMock.mockImplementation(async () => new Response(JSON.stringify(body), { status }));
}

function lastCall(): { url: URL; method?: string; body?: unknown } {
	const [url, init] = fetchMock.mock.calls.at(-1)!;
	return {
		url: new URL(String(url), "http://x"),
		method: init?.method,
		body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body,
	};
}

const ENVELOPE = {
	data: { name: "D-1", modified: "2026-09-18 10:00:00.000000", modified_by: "ann@example.com" },
	permissions: { read: 1, write: 1 },
	assignments: [{ user: "bob@example.com", description: "Call back" }],
	shares: [{ user: "everyone", read: 1 }],
	tags: ["urgent"],
	favourites: [{ user: "ann@example.com" }],
	follows: true,
	users: { "ann@example.com": { full_name: "Ann", user_image: "/ann.png" } },
	link_titles: { "CRM Lead::L-1": "Lead One" },
	seen: ["ann@example.com"],
};

beforeEach(() => {
	vi.stubGlobal("fetch", fetchMock);
	fetchMock.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe("loadRecord", () => {
	it("reads the document with every part the page draws, and marks it seen", async () => {
		respond(ENVELOPE);
		const loaded = await loadRecord("CRM Deal", "D-1");
		const { url, method } = lastCall();
		expect(method).toBe("GET");
		expect(url.pathname).toBe("/api/v2/document/CRM%20Deal/D-1");
		expect(url.searchParams.get("include")!.split(",")).toEqual([
			"permissions",
			"assignments",
			"shares",
			"tags",
			"favourites",
			"follows",
			"users",
			"link_titles",
			"seen",
		]);
		expect(loaded.document).toEqual(ENVELOPE.data);
		expect(loaded.docinfo).toEqual({
			permissions: ENVELOPE.permissions,
			assignments: ENVELOPE.assignments,
			shares: ENVELOPE.shares,
			tags: ENVELOPE.tags,
			favourites: ENVELOPE.favourites,
			follows: true,
			users: ENVELOPE.users,
		});
		expect(loaded.linkTitles).toEqual(ENVELOPE.link_titles);
	});

	it("throws the wrapper's error for a refused read", async () => {
		respond({ errors: [{ type: "PermissionError", message: "Not permitted" }] }, 403);
		await expect(loadRecord("CRM Deal", "D-1")).rejects.toMatchObject({
			name: "ApiError",
			status: 403,
		});
	});
});

describe("loadParts", () => {
	it("reads the same parts without marking the record seen, and hands back the parts alone", async () => {
		respond(ENVELOPE);
		const parts = await loadParts("CRM Deal", "D-1");
		const include = lastCall().url.searchParams.get("include")!.split(",");
		expect(include).not.toContain("seen");
		expect(include).toContain("shares");
		expect(parts.tags).toEqual(["urgent"]);
		expect(parts.follows).toBe(true);
		expect(parts).not.toHaveProperty("document");
	});
});

describe("saveRecord", () => {
	it("patches the whole document, carrying modified, and hands back the saved one", async () => {
		const saved = { ...ENVELOPE.data, status: "Won", modified: "2026-09-18 10:01:00.000000" };
		respond({ data: saved });
		const draft = { ...ENVELOPE.data, status: "Won" };
		expect(await saveRecord("CRM Deal", draft)).toEqual(saved);
		const { url, method, body } = lastCall();
		expect(method).toBe("PATCH");
		expect(url.pathname).toBe("/api/v2/document/CRM%20Deal/D-1");
		expect(body).toEqual({ ...draft, doctype: "CRM Deal" });
		expect((body as any).modified).toBe(ENVELOPE.data.modified);
	});

	it("refuses a draft without modified before any request", async () => {
		await expect(saveRecord("CRM Deal", { name: "D-1" })).rejects.toMatchObject({ name: "ApiError" });
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it("names a conflict as the wrapper does", async () => {
		respond({ errors: [{ type: "TimestampMismatchError", message: "Stale" }] }, 409);
		await expect(saveRecord("CRM Deal", ENVELOPE.data)).rejects.toMatchObject({
			isTimestampMismatch: true,
		});
	});
});
