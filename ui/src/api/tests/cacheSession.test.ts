import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RECORD_PARTS, clearDataCache, readCachedDocument } from "../../cache";
import { resetSession, setSession, useSession } from "../../composables/useSession";
import { getDocument, type Session } from "../index";

const OLD = "2026-09-01 10:00:00.000000";

const fetchMock = vi.fn<typeof fetch>();

function respond(body: unknown) {
  fetchMock.mockImplementationOnce(async () => new Response(JSON.stringify(body)));
}

function as(name: string) {
  return { user: { name }, roles: [] } as unknown as Session;
}

async function readRecord(name: string) {
  const parts = Object.fromEntries(RECORD_PARTS.map((part) => [part, []]));
  respond({ data: { name, modified: OLD }, ...parts });
  await getDocument("ToDo", name, { include: RECORD_PARTS });
}

function cached(name: string) {
  return readCachedDocument("ToDo", name);
}

beforeEach(() => {
  resetSession();
  clearDataCache();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe("a session the host publishes", () => {
  it("clears the cache when the user changes, and only then", async () => {
    setSession(as("ann@example.com"));
    await readRecord("T-1");
    setSession(as("ann@example.com"));
    expect(cached("T-1")).toBeDefined();
    setSession(as("bo@example.com"));
    expect(cached("T-1")).toBeUndefined();
  });

  it("keeps the cache when it is the first session", async () => {
    await readRecord("T-1");
    setSession(as("ann@example.com"));
    expect(cached("T-1")).toBeDefined();
  });
});

describe("a session the reload fetches", () => {
  it("clears the cache when the user changes, and only then", async () => {
    setSession(as("ann@example.com"));
    await readRecord("T-1");
    respond({ data: as("ann@example.com") });
    await useSession().reload();
    expect(cached("T-1")).toBeDefined();
    respond({ data: as("bo@example.com") });
    await useSession().reload();
    expect(cached("T-1")).toBeUndefined();
  });

  it("keeps the cache when it is the first session", async () => {
    await readRecord("T-1");
    fetchMock.mockImplementation(async () => new Response(JSON.stringify({ data: as("ann") })));
    const { session, reload } = useSession();
    await reload();
    expect(session.value?.user.name).toBe("ann");
    expect(cached("T-1")).toBeDefined();
  });
});

describe("a reset", () => {
  it("clears the cache", async () => {
    await readRecord("T-1");
    resetSession();
    expect(cached("T-1")).toBeUndefined();
  });
});
