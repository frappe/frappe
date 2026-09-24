import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import * as cache from "../../cache";
import { RECORD_PARTS, clearDataCache, readCachedDocument, readCachedList } from "../../cache";
import {
  addAssignment,
  addTag,
  copyDocument,
  countDocuments,
  createDocument,
  deleteDocument,
  getDocument,
  listDocuments,
  removeTag,
  runDocumentMethod,
  updateDocument,
} from "../index";

vi.mock("../../cache", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../cache")>();
  return {
    ...actual,
    feedDocsDocument: vi.fn(actual.feedDocsDocument),
    feedDocumentWrite: vi.fn(actual.feedDocumentWrite),
    feedListRead: vi.fn(actual.feedListRead),
    feedReadError: vi.fn(actual.feedReadError),
    feedRecordRead: vi.fn(actual.feedRecordRead),
    settleTicket: vi.fn(actual.settleTicket),
    takeTicket: vi.fn(actual.takeTicket),
  };
});

const OLD = "2026-09-01 10:00:00.000000";
const MIDDLE = "2026-09-02 10:00:00.000000";
const NEW = "2026-09-03 10:00:00.000000";
const LIST = { fields: ["name", "status"], filters: { status: "Open" } };

const ALL_PARTS = Object.fromEntries(RECORD_PARTS.map((part) => [part, []]));

const fetchMock = vi.fn<typeof fetch>();

function respond(body: unknown, status = 200) {
  fetchMock.mockImplementationOnce(async () => new Response(JSON.stringify(body), { status }));
}

/** The next request waits until the returned function answers it. */
function respondLater(): (body: unknown, status?: number) => void {
  let answer!: (response: Response) => void;
  fetchMock.mockImplementationOnce(() => new Promise((resolve) => (answer = resolve)));
  return (body, status = 200) => answer(new Response(JSON.stringify(body), { status }));
}

function sentQuery(): URLSearchParams {
  return new URL(String(fetchMock.mock.calls.at(-1)![0]), "http://x").searchParams;
}

function cached(name: string) {
  return readCachedDocument("ToDo", name);
}

/** Asks for every record part; `parts` overrides some of their values. */
async function readRecord(name: string, modified: string, parts: Record<string, unknown> = {}) {
  const sent = { ...ALL_PARTS, ...parts };
  respond({ data: { name, modified, status: "Open" }, ...sent });
  await getDocument("ToDo", name, { include: Object.keys(sent) });
}

async function readList(names: string[], count?: number) {
  const data = names.map((name) => ({ name, status: "Open", modified: OLD }));
  respond({ data, has_next_page: false, ...(count === undefined ? {} : { count }) });
  await listDocuments("ToDo", LIST, { include: count === undefined ? [] : ["count"] });
}

beforeEach(() => {
  clearDataCache();
  vi.clearAllMocks();
  vi.restoreAllMocks();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe("reads", () => {
  it("getDocument feeds a complete entry with the parts it asked for", async () => {
    const body = { data: { name: "T-1", modified: OLD }, ...ALL_PARTS, tags: ["a"], seen: true };
    respond(body);
    const include = [...RECORD_PARTS, "seen"].join(", ");
    const envelope = await getDocument("ToDo", "T-1", { include });
    expect(envelope).toEqual(body);
    expect(Object.isFrozen(envelope.data)).toBe(false);
    expect(cached("T-1")).toMatchObject({ complete: true, parts: { tags: ["a"] } });
    expect(cached("T-1")!.parts).not.toHaveProperty("seen");
  });

  it("listDocuments sends modified and feeds the list under the caller's query", async () => {
    const body = { data: [{ name: "T-1", status: "Open", modified: OLD }], has_next_page: true };
    respond(body);
    expect(await listDocuments("ToDo", LIST)).toEqual(body);
    expect(JSON.parse(sentQuery().get("fields")!)).toEqual(["name", "status", "modified"]);
    expect(readCachedList("ToDo", LIST)).toMatchObject({ names: ["T-1"], hasNextPage: true });
  });

  it("asks for name and modified when the caller names no fields", async () => {
    respond({ data: [{ name: "T-1", modified: OLD }], has_next_page: false });
    await listDocuments("ToDo", { limit: 5 });
    expect(JSON.parse(sentQuery().get("fields")!)).toEqual(["name", "modified"]);
    expect(readCachedList("ToDo", { limit: 20 })!.names).toEqual(["T-1"]);
  });

  it("leaves a grouped read's fields alone and feeds nothing from it", async () => {
    const query = { fields: ["status", "count(name) as total"], group_by: "status" };
    respond({ data: [{ status: "Open", total: 3 }], has_next_page: false });
    await listDocuments("ToDo", query);
    expect(JSON.parse(sentQuery().get("fields")!)).toEqual(query.fields);
    expect(readCachedList("ToDo", query)).toBeUndefined();
  });

  it("leaves a star read's fields alone", async () => {
    respond({ data: [], has_next_page: false });
    await listDocuments("ToDo", { fields: ["*"] });
    expect(JSON.parse(sentQuery().get("fields")!)).toEqual(["*"]);
  });

  it("getDocument with no include stores nothing new and completes nothing", async () => {
    await readList(["T-1"]);
    respond({ data: { name: "T-1", modified: OLD, status: "Open" } });
    await getDocument("ToDo", "T-1");
    respond({ data: { name: "T-2", modified: OLD } });
    await getDocument("ToDo", "T-2");
    expect(cached("T-1")!.complete).toBe(false);
    expect(cached("T-2")).toBeUndefined();
  });
});

describe("writes", () => {
  it("updateDocument feeds the saved doc and leaves list names alone", async () => {
    await readList(["T-1", "T-2"]);
    await readRecord("T-1", OLD, { tags: [] });
    const body = { data: { name: "T-1", modified: NEW, status: "Closed" } };
    respond(body);
    expect(await updateDocument("ToDo", "T-1", { name: "T-1", modified: OLD })).toEqual(body);
    expect(cached("T-1")).toMatchObject({ complete: true, doc: { status: "Closed" } });
    expect(readCachedList("ToDo", LIST)!.names).toEqual(["T-1", "T-2"]);
  });

  it("createDocument feeds the new doc and returns the reply", async () => {
    const body = { data: { name: "T-9", modified: NEW } };
    respond(body);
    expect(await createDocument("ToDo", { description: "x" })).toEqual(body);
    expect(cache.feedDocumentWrite).toHaveBeenCalledWith(expect.any(Number), "ToDo", body.data);
  });

  it("deleteDocument drops the entry, its name from lists, and one from the count", async () => {
    await readList(["T-1", "T-2"], 2);
    respond({ data: "ok" });
    expect(await deleteDocument("ToDo", "T-1")).toEqual({ data: "ok" });
    expect(cached("T-1")).toBeUndefined();
    expect(readCachedList("ToDo", LIST)).toMatchObject({ names: ["T-2"], count: 1 });
  });

  it("copyDocument feeds nothing: the copy has no name until it is saved", async () => {
    respond({ data: { doctype: "ToDo", status: "Open" } });
    await copyDocument("ToDo", "T-1");
    expect(cache.feedDocumentWrite).not.toHaveBeenCalled();
    expect(cache.feedRecordRead).not.toHaveBeenCalled();
  });
});

describe("part writes", () => {
  beforeEach(() => readRecord("T-1", OLD, { assignments: [], tags: [] }));

  it("addAssignment feeds the assignments and _assign", async () => {
    const body = { data: { assignments: [{ user: "ann@example.com" }], users: {} } };
    respond(body);
    expect(await addAssignment("ToDo", "T-1", { user: "ann@example.com" })).toEqual(body);
    expect(cached("T-1")!.parts.assignments).toEqual(body.data.assignments);
    expect(cached("T-1")!.doc._assign).toBe('["ann@example.com"]');
  });

  it("addTag and removeTag feed the tags and _user_tags", async () => {
    respond({ data: { tags: ["a", "b"] } });
    expect(await addTag("ToDo", "T-1", "b")).toEqual({ data: { tags: ["a", "b"] } });
    expect(cached("T-1")!.doc._user_tags).toBe("a,b");
    respond({ data: { tags: ["b"] } });
    await removeTag("ToDo", "T-1", "a");
    expect(cached("T-1")!.parts.tags).toEqual(["b"]);
  });
});

describe("a reply's docs", () => {
  it("feeds each document in it", async () => {
    await readRecord("T-1", OLD);
    const saved = { doctype: "ToDo", name: "T-1", modified: NEW, status: "Closed" };
    respond({ data: null, docs: [saved] });
    await runDocumentMethod("ToDo", "T-1", "close");
    expect(cached("T-1")!.doc).toMatchObject({ modified: NEW, status: "Closed" });
  });

  it("skips a document the method did not save", async () => {
    await readRecord("T-1", OLD);
    const unsaved = { doctype: "ToDo", name: "T-1", modified: OLD, status: "Unsaved" };
    respond({ data: null, docs: [unsaved] });
    await runDocumentMethod("ToDo", "T-1", "set_status");
    expect(cached("T-1")!.doc.status).toBe("Open");
  });

  it("drops a document from a call sent before a save that landed first", async () => {
    await readRecord("T-1", OLD);
    const answerMethod = respondLater();
    const method = runDocumentMethod("ToDo", "T-1", "close");
    respond({ data: { name: "T-1", modified: NEW, status: "Saved" } });
    await updateDocument("ToDo", "T-1", { name: "T-1", modified: OLD });
    answerMethod({ data: null, docs: [{ doctype: "ToDo", name: "T-1", modified: MIDDLE }] });
    await method;
    expect(cached("T-1")!.doc).toMatchObject({ modified: NEW, status: "Saved" });
  });
});

describe("failures", () => {
  it.each([403, 404])("a %i on getDocument removes the entry and still throws", async (status) => {
    await readRecord("T-1", OLD);
    respond({ errors: [{ type: "DoesNotExistError" }] }, status);
    await expect(getDocument("ToDo", "T-1")).rejects.toMatchObject({ status });
    expect(cached("T-1")).toBeUndefined();
  });

  it("a 404 answered after a newer read landed leaves the entry", async () => {
    const answerFirst = respondLater();
    const first = getDocument("ToDo", "T-1");
    await readRecord("T-1", NEW);
    answerFirst({ errors: [{ type: "DoesNotExistError" }] }, 404);
    await expect(first).rejects.toMatchObject({ status: 404 });
    expect(cached("T-1")!.doc.modified).toBe(NEW);
  });

  it("a failed request feeds nothing", async () => {
    await readRecord("T-1", OLD);
    vi.clearAllMocks();
    respond({ errors: [{ type: "ValidationError" }] }, 417);
    await expect(updateDocument("ToDo", "T-1", { name: "T-1", modified: OLD })).rejects.toThrow();
    respond({ errors: [{ type: "PermissionError" }] }, 403);
    await expect(listDocuments("ToDo", LIST)).rejects.toThrow();
    expect(cache.feedDocumentWrite).not.toHaveBeenCalled();
    expect(cache.feedListRead).not.toHaveBeenCalled();
    expect(cached("T-1")!.doc.modified).toBe(OLD);
  });
});

describe("tickets", () => {
  const byNumber = (first: number, second: number) => first - second;

  function expectEachSettledOnceAfterItsFeeds() {
    const taken = vi.mocked(cache.takeTicket).mock.results.map((result) => result.value as number);
    const settle = vi.mocked(cache.settleTicket).mock;
    expect(settle.calls.map(([ticket]) => ticket).sort(byNumber)).toEqual(taken.sort(byNumber));
    const feeds = [
      cache.feedRecordRead,
      cache.feedListRead,
      cache.feedDocumentWrite,
      cache.feedDocsDocument,
      cache.feedReadError,
    ] as unknown as Mock[];
    for (const { mock } of feeds) {
      mock.calls.forEach(([ticket], index) => {
        const settledAt = settle.invocationCallOrder[settle.calls.findIndex(([t]) => t === ticket)];
        expect(settledAt).toBeGreaterThan(mock.invocationCallOrder[index]);
      });
    }
  }

  it("settles each ticket once, after its reply or failure is fed", async () => {
    await readRecord("T-1", OLD);
    await readList(["T-1"]);
    respond({ data: { name: "T-1", modified: NEW } });
    await updateDocument("ToDo", "T-1", { name: "T-1", modified: OLD });
    respond({ data: null, docs: [{ doctype: "ToDo", name: "T-1", modified: NEW }] });
    await runDocumentMethod("ToDo", "T-1", "close");
    respond({ errors: [{ type: "DoesNotExistError" }] }, 404);
    await expect(getDocument("ToDo", "T-1")).rejects.toMatchObject({ status: 404 });
    respond({ errors: [{ type: "ValidationError" }] }, 417);
    await expect(deleteDocument("ToDo", "T-1")).rejects.toThrow();
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    await expect(countDocuments("ToDo")).rejects.toThrow();
    expect(cache.takeTicket).toHaveBeenCalledTimes(7);
    expect(cache.feedReadError).toHaveBeenCalledTimes(1);
    expectEachSettledOnceAfterItsFeeds();
  });
});

describe("a fault in the cache", () => {
  function catchRethrow() {
    const rethrown: (() => void)[] = [];
    vi.spyOn(globalThis, "queueMicrotask").mockImplementation((task) => rethrown.push(task));
    return rethrown;
  }

  it("empties the cache, rethrows on its own, and the request still answers", async () => {
    await readRecord("T-1", OLD);
    vi.mocked(cache.feedListRead).mockImplementationOnce(() => {
      throw new Error("cache fault");
    });
    const rethrown = catchRethrow();
    const body = { data: [{ name: "T-1", status: "Open", modified: OLD }], has_next_page: false };
    respond(body);
    expect(await listDocuments("ToDo", LIST)).toEqual(body);
    expect(cached("T-1")).toBeUndefined();
    expect(rethrown).toHaveLength(1);
    expect(rethrown[0]).toThrow("cache fault");
  });

  it("in a reply's docs does not fail the call", async () => {
    vi.mocked(cache.feedDocsDocument).mockImplementationOnce(() => {
      throw new Error("cache fault");
    });
    const rethrown = catchRethrow();
    respond({ data: "done", docs: [{ doctype: "ToDo", name: "T-1", modified: NEW }] });
    expect(await runDocumentMethod("ToDo", "T-1", "close")).toMatchObject({ data: "done" });
    expect(rethrown[0]).toThrow("cache fault");
  });
});
