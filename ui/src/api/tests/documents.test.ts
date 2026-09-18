import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  copyDocument,
  countDocuments,
  createDocument,
  deleteDocument,
  getDocument,
  getMeta,
  listDocuments,
  runDocumentMethod,
  runMethod,
  searchDocuments,
  TIMESTAMP_MISMATCH,
  updateDocument,
} from "../index";

const fetchMock = vi.fn<typeof fetch>();

function respond(body: unknown, status = 200) {
  fetchMock.mockImplementation(async () => new Response(JSON.stringify(body), { status }));
}

function lastCall(): { url: string; method?: string; body?: unknown } {
  const [url, init] = fetchMock.mock.calls.at(-1)!;
  return {
    url: String(url),
    method: init?.method,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body,
  };
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe("getDocument", () => {
  it("reads the document alone", async () => {
    respond({ data: { name: "T-1" } });
    const { data } = await getDocument("ToDo", "T-1");
    expect(data.name).toBe("T-1");
    expect(lastCall()).toMatchObject({ url: "/api/v2/document/ToDo/T-1", method: "GET" });
  });

  it("asks for the named parts as one comma-joined include, and returns them beside data", async () => {
    respond({ data: { name: "T-1" }, permissions: { read: 1 }, comments: [] });
    const envelope = await getDocument("ToDo", "T-1", { include: ["permissions", "comments"] });
    expect(lastCall().url).toBe("/api/v2/document/ToDo/T-1?include=permissions%2Ccomments");
    expect(envelope.permissions).toEqual({ read: 1 });
    expect(envelope.comments).toEqual([]);
  });

  it("encodes the doctype and the name", async () => {
    respond({ data: {} });
    await getDocument("Sales Order", "SO/2026/#1");
    expect(lastCall().url).toBe("/api/v2/document/Sales%20Order/SO%2F2026%2F%231");
  });
});

describe("listDocuments and countDocuments", () => {
  it("passes filters and or_filters through untouched, as JSON", async () => {
    respond({ data: [{ name: "T-1" }], has_next_page: false });
    const filters = { status: "Open", priority: ["in", ["High", "Medium"]] };
    const or_filters = [["owner", "=", "a@x.com"], ["assigned_to", "=", "a@x.com"]];
    const envelope = await listDocuments("ToDo", {
      fields: ["name", "status"],
      filters,
      or_filters,
      order_by: "modified desc",
      start: 20,
      limit: 20,
    });
    expect(envelope.has_next_page).toBe(false);
    const query = new URL(lastCall().url, "http://x").searchParams;
    expect(JSON.parse(query.get("filters")!)).toEqual(filters);
    expect(JSON.parse(query.get("or_filters")!)).toEqual(or_filters);
    expect(query.get("start")).toBe("20");
  });

  it("carries no count keys when include did not ask for one", async () => {
    respond({ data: [], has_next_page: false });
    const envelope = await listDocuments("ToDo", { limit: 20 });
    expect(lastCall().url).toBe("/api/v2/document/ToDo?limit=20");
    expect("count" in envelope).toBe(false);
    expect("count_capped" in envelope).toBe(false);
  });

  it("asks for the count as an include, from an array or a string", async () => {
    respond({ data: [{ name: "T-1" }], has_next_page: true, count: 41, count_capped: false });
    const envelope = await listDocuments("ToDo", { limit: 1 }, { include: ["count"] });
    expect(lastCall().url).toBe("/api/v2/document/ToDo?limit=1&include=count");
    expect(envelope.count).toBe(41);
    expect(envelope.count_capped).toBe(false);
    await listDocuments("ToDo", {}, { include: "count,permissions" });
    expect(lastCall().url).toBe("/api/v2/document/ToDo?include=count%2Cpermissions");
  });

  it("passes a null count through when the server gave up counting", async () => {
    respond({ data: [], has_next_page: false, count: null, count_capped: false });
    const envelope = await listDocuments("ToDo", {}, { include: ["count"] });
    expect(envelope.count).toBeNull();
  });

  it("counts on the doctype route", async () => {
    respond({ data: 7 });
    const { data } = await countDocuments("ToDo", { filters: { status: "Open" } });
    expect(data).toBe(7);
    expect(lastCall().url).toBe("/api/v2/doctype/ToDo/count?filters=%7B%22status%22%3A%22Open%22%7D");
  });

  it("counts with or_filters and no limit, and passes a null count through", async () => {
    respond({ data: null });
    const or_filters = [["owner", "=", "a@x.com"], ["assigned_to", "=", "a@x.com"]];
    const { data } = await countDocuments("ToDo", { or_filters });
    expect(data).toBeNull();
    const query = new URL(lastCall().url, "http://x").searchParams;
    expect(JSON.parse(query.get("or_filters")!)).toEqual(or_filters);
    expect(query.has("limit")).toBe(false);
  });
});

describe("searchDocuments", () => {
  it("searches on the doctype route with every param by its server name", async () => {
    respond({ data: [{ value: "a@x.com", label: "A", description: "A (a@x.com)" }] });
    const { data } = await searchDocuments("User", {
      txt: "a",
      filters: { enabled: 1 },
      reference_doctype: "ToDo",
      query: "frappe.core.doctype.user.user.user_query",
      limit: 10,
      start: 0,
    });
    expect(data[0].value).toBe("a@x.com");
    const { pathname, searchParams: query } = new URL(lastCall().url, "http://x");
    expect(pathname).toBe("/api/v2/doctype/User/search");
    expect(query.get("txt")).toBe("a");
    expect(JSON.parse(query.get("filters")!)).toEqual({ enabled: 1 });
    expect(query.get("reference_doctype")).toBe("ToDo");
    expect(query.get("query")).toBe("frappe.core.doctype.user.user.user_query");
    expect(query.get("limit")).toBe("10");
    expect(query.get("start")).toBe("0");
  });
});

describe("updateDocument", () => {
  it("PATCHes the whole document with its modified stamp", async () => {
    respond({ data: { name: "T-1", modified: "2026-09-17 10:00:01.000000" } });
    const doc = { name: "T-1", status: "Closed", modified: "2026-09-17 10:00:00.000000" };
    await updateDocument("ToDo", "T-1", doc);
    expect(lastCall()).toMatchObject({
      url: "/api/v2/document/ToDo/T-1",
      method: "PATCH",
      body: doc,
    });
  });

  it("refuses a document without modified, before any request", async () => {
    await expect(
      updateDocument("ToDo", "T-1", { name: "T-1", status: "Closed" })
    ).rejects.toMatchObject({ name: "ApiError", type: "MissingModified" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces a timestamp conflict by its error type", async () => {
    respond({ errors: [{ type: TIMESTAMP_MISMATCH, message: "Modified by someone else" }] }, 409);
    await expect(
      updateDocument("ToDo", "T-1", { name: "T-1", modified: "2026-09-17 10:00:00.000000" })
    ).rejects.toMatchObject({ type: TIMESTAMP_MISMATCH, isTimestampMismatch: true });
  });
});

describe("create, delete and copy", () => {
  it("creates on the collection route", async () => {
    respond({ data: { name: "T-2" } });
    await createDocument("ToDo", { description: "x" });
    expect(lastCall()).toMatchObject({
      url: "/api/v2/document/ToDo",
      method: "POST",
      body: { description: "x" },
    });
  });

  it("deletes with the DELETE method", async () => {
    respond({ data: "ok" }, 202);
    expect((await deleteDocument("ToDo", "T-1")).data).toBe("ok");
    expect(lastCall()).toMatchObject({ url: "/api/v2/document/ToDo/T-1", method: "DELETE" });
  });

  it("copies from the copy route", async () => {
    respond({ data: { description: "x" } });
    await copyDocument("ToDo", "T-1");
    expect(lastCall()).toMatchObject({ url: "/api/v2/document/ToDo/T-1/copy", method: "GET" });
  });
});

describe("methods and meta", () => {
  it("runs a dotted method as a POST with the arguments in the body", async () => {
    respond({ data: { ok: 1 } });
    await runMethod("frappe.desk.search.search_link", { doctype: "User", txt: "a" });
    expect(lastCall()).toMatchObject({
      url: "/api/v2/method/frappe.desk.search.search_link",
      method: "POST",
      body: { doctype: "User", txt: "a" },
    });
  });

  it("runs a dotted method as a GET with the arguments in the query when asked", async () => {
    respond({ data: [] });
    await runMethod("frappe.desk.search.search_link", { doctype: "User" }, { http: "GET" });
    expect(lastCall()).toMatchObject({
      url: "/api/v2/method/frappe.desk.search.search_link?doctype=User",
      method: "GET",
    });
  });

  it("runs a document method on the document's method route", async () => {
    respond({ data: null });
    await runDocumentMethod("ToDo", "T-1", "close", { reason: "done" });
    expect(lastCall()).toMatchObject({
      url: "/api/v2/document/ToDo/T-1/method/close",
      method: "POST",
      body: { reason: "done" },
    });
  });

  it("reads meta, with children when asked", async () => {
    respond({ data: { name: "ToDo" } });
    await getMeta("ToDo");
    expect(lastCall().url).toBe("/api/v2/doctype/ToDo/meta");
    await getMeta("ToDo", { include: ["children"] });
    expect(lastCall().url).toBe("/api/v2/doctype/ToDo/meta?include=children");
  });
});
