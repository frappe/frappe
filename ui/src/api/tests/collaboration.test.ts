import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  addAssignment,
  addComment,
  addFavourite,
  addFollow,
  addShare,
  addTag,
  removeAssignment,
  removeComment,
  removeFavourite,
  removeFollow,
  removeShare,
  removeTag,
  updateComment,
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

const RECORD = "/api/v2/document/ToDo/T-1";

describe("assignments", () => {
  it("POSTs one user with the optional fields, and hands back the part with its users", async () => {
    const users = { "ann@example.com": { full_name: "Ann" } };
    respond({ data: { assignments: [{ user: "ann@example.com" }], users } });
    const { data } = await addAssignment("ToDo", "T-1", {
      user: "ann@example.com",
      description: "Call back",
    });
    expect(data.assignments).toEqual([{ user: "ann@example.com" }]);
    expect(data.users).toEqual(users);
    expect(lastCall()).toMatchObject({
      url: `${RECORD}/assignments`,
      method: "POST",
      body: { user: "ann@example.com", description: "Call back" },
    });
  });

  it("DELETEs by the user in the path", async () => {
    respond({ data: { assignments: [] } });
    await removeAssignment("ToDo", "T-1", "ann@example.com");
    expect(lastCall()).toMatchObject({
      url: `${RECORD}/assignments/ann%40example.com`,
      method: "DELETE",
    });
  });
});

describe("shares", () => {
  it("POSTs the rights as the body", async () => {
    respond({ data: { shares: [] } });
    await addShare("ToDo", "T-1", { user: "bob@example.com", read: 1, write: 1 });
    expect(lastCall()).toMatchObject({
      url: `${RECORD}/shares`,
      method: "POST",
      body: { user: "bob@example.com", read: 1, write: 1 },
    });
  });

  it("DELETEs a person's share, and the everyone share by its reserved name", async () => {
    respond({ data: { shares: [] } });
    await removeShare("ToDo", "T-1", "bob@example.com");
    expect(lastCall()).toMatchObject({
      url: `${RECORD}/shares/bob%40example.com`,
      method: "DELETE",
    });
    await removeShare("ToDo", "T-1", "everyone");
    expect(lastCall()).toMatchObject({ url: `${RECORD}/shares/everyone`, method: "DELETE" });
  });
});

describe("tags", () => {
  it("POSTs the tag in the body and DELETEs it from the path, encoded", async () => {
    respond({ data: { tags: ["a/b"] } });
    await addTag("ToDo", "T-1", "a/b");
    expect(lastCall()).toMatchObject({
      url: `${RECORD}/tags`,
      method: "POST",
      body: { tag: "a/b" },
    });
    await removeTag("ToDo", "T-1", "a/b");
    expect(lastCall()).toMatchObject({ url: `${RECORD}/tags/a%2Fb`, method: "DELETE" });
  });
});

describe("favourites and follows", () => {
  it("take no key and send no body", async () => {
    respond({ data: { favourites: [] } });
    await addFavourite("ToDo", "T-1");
    expect(lastCall()).toMatchObject({
      url: `${RECORD}/favourites`,
      method: "POST",
      body: undefined,
    });
    await removeFavourite("ToDo", "T-1");
    expect(lastCall()).toMatchObject({ url: `${RECORD}/favourites`, method: "DELETE" });
    respond({ data: { follows: true } });
    expect((await addFollow("ToDo", "T-1")).data.follows).toBe(true);
    expect(lastCall()).toMatchObject({ url: `${RECORD}/follows`, method: "POST" });
    respond({ data: { follows: false } });
    expect((await removeFollow("ToDo", "T-1")).data.follows).toBe(false);
    expect(lastCall()).toMatchObject({ url: `${RECORD}/follows`, method: "DELETE" });
  });
});

describe("comments", () => {
  it("POSTs, PATCHes by name and DELETEs by name", async () => {
    respond({ data: { comments: [] } });
    await addComment("ToDo", "T-1", "hello");
    expect(lastCall()).toMatchObject({
      url: `${RECORD}/comments`,
      method: "POST",
      body: { content: "hello" },
    });
    await updateComment("ToDo", "T-1", "c1", "edited");
    expect(lastCall()).toMatchObject({
      url: `${RECORD}/comments/c1`,
      method: "PATCH",
      body: { content: "edited" },
    });
    await removeComment("ToDo", "T-1", "c1");
    expect(lastCall()).toMatchObject({ url: `${RECORD}/comments/c1`, method: "DELETE" });
  });

  it("sends the attachments and reads the added comment's name", async () => {
    respond({ data: { comments: [], added: "c2" } });
    const answer = await addComment("ToDo", "T-1", "see files", { attachments: ["f1", "f2"] });
    expect(lastCall().body).toEqual({ content: "see files", attachments: ["f1", "f2"] });
    expect(answer.data.added).toBe("c2");
  });
});

describe("the path", () => {
  it("encodes a slashed record name so the part and key stay their own segments", async () => {
    respond({ data: { tags: [] } });
    await removeTag("Sales Order", "SO/2026/#1", "x");
    expect(lastCall().url).toBe("/api/v2/document/Sales%20Order/SO%2F2026%2F%231/tags/x");
  });
});
