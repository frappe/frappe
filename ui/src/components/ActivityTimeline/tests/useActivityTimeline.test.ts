import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";
import type { Activity } from "../types";

const api = vi.hoisted(() => ({ getDocumentPart: vi.fn() }));
const socket = vi.hoisted(() => {
  const handlers: Record<string, Set<(payload: unknown) => void>> = {};
  const on = (event: string, handler: (payload: unknown) => void) =>
    (handlers[event] ??= new Set()).add(handler);
  const off = (event: string, handler: (payload: unknown) => void) =>
    handlers[event]?.delete(handler);
  const emit = (event: string, payload: unknown) =>
    handlers[event]?.forEach((handler) => handler(payload));
  return { instance: { on, off }, emit, ready: true };
});
vi.mock("../../../api", () => ({ getDocumentPart: api.getDocumentPart }));
vi.mock("../../../socket", () => ({
  getSocketInstance: () => (socket.ready ? socket.instance : undefined),
  subscribeToDoc: () => () => {},
}));

import {
  activityTimelineRows,
  endActivityPrefetch,
  prefetchActivityTimeline,
  reloadActivityTimeline,
  useActivityTimeline,
} from "../useActivityTimeline";
import { addPendingActivity } from "../pendingRows";
import ActivityTimeline from "../ActivityTimeline.vue";

let docCounter = 0;
/** A fresh document per test: the composable keeps one store per document for the session. */
function freshDoc() {
  return `T-${docCounter++}`;
}

function row(type: Activity["type"], key: string, timestamp: string, data = {}): Activity {
  return { type, key, timestamp, author: { email: "a@x.com", fullname: "A" }, data } as Activity;
}

const c = (n: number) => row("comment", `comment:${n}`, `2026-01-0${n}`);

type Page = { activities: Activity[]; next: string | null };

/** Answers each read by its `before` cursor; the newest page sits under "newest". */
function serve(pages: Record<string, Page | Promise<Page>>) {
  api.getDocumentPart.mockImplementation(async (_dt, _name, _part, params) => {
    const page = pages[params.before ?? "newest"];
    if (!page) throw new Error(`no page for ${params.before}`);
    return { data: await page };
  });
}

/** A comment the socket publishes, as `docinfo_update` carries it. */
function socketComment(docname: string, name: string, text: string, creation = "2026-01-05 10:00:02") {
  return {
    key: "comments",
    action: "add",
    doc: {
      name,
      reference_doctype: "ToDo",
      reference_name: docname,
      content: `<p>${text}</p>`,
      creation,
      owner: "a@x.com",
    },
  };
}

const keys = (timeline: ReturnType<typeof useActivityTimeline>) =>
  timeline.activities.value.map((a) => a.key);

const mounted: App[] = [];
/** Mounts a host so the store subscribes to the socket, as a tab body would. */
function mountTimeline(name: string, types?: Parameters<typeof useActivityTimeline>[2]) {
  let timeline!: ReturnType<typeof useActivityTimeline>;
  const Host = defineComponent({
    setup() {
      timeline = useActivityTimeline("ToDo", name, types);
      return () => h(ActivityTimeline, { activities: timeline.activities.value });
    },
  });
  const el = document.createElement("div");
  const app = createApp(Host);
  app.mount(el);
  mounted.push(app);
  return { timeline, el };
}

beforeEach(() => {
  socket.ready = true;
  api.getDocumentPart.mockReset();
  serve({ newest: { activities: [], next: null } });
});

afterEach(() => {
  mounted.splice(0).forEach((app) => app.unmount());
  vi.useRealTimers();
});

describe("useActivityTimeline paging", () => {
  it("reads the newest page with the visible types and the server's page size", async () => {
    const name = freshDoc();
    serve({
      newest: {
        activities: [row("comment", "comment:1", "2026-01-02"), row("email", "email:1", "2026-01-03")],
        next: "c1",
      },
    });
    const timeline = useActivityTimeline("ToDo", name, ["comment", "email"]);
    expect(api.getDocumentPart.mock.calls[0][3]).toStrictEqual({
      types: ["comment", "email"],
      before: undefined,
    });
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));
    expect(keys(timeline)).toEqual(["comment:1", "email:1"]);
    expect(timeline.paginate.hasNextPage).toBe(true);
  });

  it("fetches the older page by cursor, prepends it without duplicates and shares one request", async () => {
    const name = freshDoc();
    serve({
      newest: { activities: [row("comment", "comment:2", "2026-01-03")], next: "c1" },
      c1: {
        activities: [row("email", "email:1", "2026-01-01"), row("comment", "comment:2", "2026-01-03")],
        next: null,
      },
    });
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.paginate.hasNextPage).toBe(true));

    const first = timeline.paginate.fetchNextPage();
    const second = timeline.paginate.fetchNextPage();
    expect(timeline.paginate.isFetchingNextPage).toBe(true);
    await Promise.all([first, second]);

    const olderReads = api.getDocumentPart.mock.calls.filter(([, , , p]) => p.before);
    expect(olderReads).toHaveLength(1);
    expect(olderReads[0][3]).toStrictEqual({ types: undefined, before: "c1" });
    expect(keys(timeline)).toEqual(["email:1", "comment:2"]);
    expect(timeline.paginate.isFetchingNextPage).toBe(false);
    expect(timeline.paginate.hasNextPage).toBe(false);
  });

  it("has no next page when the first page ends the list, and fetches nothing", async () => {
    const name = freshDoc();
    serve({ newest: { activities: [row("comment", "comment:1", "2026-01-01")], next: null } });
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));
    expect(timeline.paginate.hasNextPage).toBe(false);
    await timeline.paginate.fetchNextPage();
    expect(api.getDocumentPart).toHaveBeenCalledTimes(1);
  });

  it("reload re-reads the newest page and keeps the older rows and the cursor", async () => {
    const name = freshDoc();
    serve({
      newest: { activities: [c(3), c(4)], next: "c3" },
      c3: { activities: [c(1), c(2)], next: "c1" },
    });
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.paginate.hasNextPage).toBe(true));
    await timeline.paginate.fetchNextPage();

    // comment:3 was deleted and comment:5 is new, so the newest page now reaches comment:2
    serve({
      newest: { activities: [c(2), c(4), c(5)], next: "c2" },
      c1: { activities: [], next: null },
    });
    await timeline.reload();
    expect(keys(timeline)).toEqual(["comment:1", "comment:2", "comment:4", "comment:5"]);

    await timeline.paginate.fetchNextPage();
    expect(api.getDocumentPart.mock.lastCall?.[3]).toMatchObject({ before: "c1" });
    expect(timeline.paginate.hasNextPage).toBe(false);
  });

  it("ends the list when an older page adds nothing and hands back its own cursor", async () => {
    const name = freshDoc();
    serve({
      newest: { activities: [row("comment", "comment:2", "2026-01-02")], next: "stuck" },
      stuck: { activities: [row("comment", "comment:2", "2026-01-02")], next: "stuck" },
    });
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.paginate.hasNextPage).toBe(true));

    await timeline.paginate.fetchNextPage();
    expect(timeline.paginate.hasNextPage).toBe(false);
    await timeline.paginate.fetchNextPage();
    expect(api.getDocumentPart).toHaveBeenCalledTimes(2);
  });

  it("drops the held rows and takes the new cursor when a reload does not reach them", async () => {
    const name = freshDoc();
    serve({ newest: { activities: [c(2), c(3)], next: "c2" } });
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.paginate.hasNextPage).toBe(true));

    // more than a page arrived since the last read: comment:4 sits between the two pages
    serve({
      newest: { activities: [c(5), c(6)], next: "c5" },
      c5: { activities: [c(3), c(4)], next: "c3" },
    });
    await timeline.reload();
    expect(keys(timeline)).toEqual(["comment:5", "comment:6"]);

    await timeline.paginate.fetchNextPage();
    expect(api.getDocumentPart.mock.lastCall?.[3]).toMatchObject({ before: "c5" });
    expect(keys(timeline)).toEqual(["comment:3", "comment:4", "comment:5", "comment:6"]);
  });

  it("gives the emails view its own store and cursor", async () => {
    const name = freshDoc();
    api.getDocumentPart.mockImplementation(async (_dt, _name, _part, params) => ({
      data: params.types
        ? { activities: [row("email", "email:1", "2026-01-02")], next: "e1" }
        : { activities: [row("comment", "comment:1", "2026-01-01")], next: null },
    }));
    const all = useActivityTimeline("ToDo", name);
    const emails = useActivityTimeline("ToDo", name, ["email"]);
    await vi.waitFor(() => expect(emails.loading.value || all.loading.value).toBe(false));

    expect(api.getDocumentPart).toHaveBeenCalledTimes(2);
    expect(api.getDocumentPart).toHaveBeenCalledWith("ToDo", name, "activity", {
      types: ["email"],
    });
    expect(keys(all)).toEqual(["comment:1"]);
    expect(keys(emails)).toEqual(["email:1"]);
    expect(all.paginate.hasNextPage).toBe(false);
    expect(emails.paginate.hasNextPage).toBe(true);
  });

  it("does not read again when a second consumer opens the same store", async () => {
    const name = freshDoc();
    const first = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(first.loading.value).toBe(false));
    useActivityTimeline("ToDo", name);
    expect(api.getDocumentPart).toHaveBeenCalledTimes(1);
  });

  it("records a failed read instead of throwing", async () => {
    const name = freshDoc();
    api.getDocumentPart.mockRejectedValue(new Error("no"));
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));
    expect(timeline.error.value).toBeInstanceOf(Error);
    expect(timeline.activities.value).toEqual([]);
    expect(timeline.paginate.hasNextPage).toBe(false);
  });

  it("keeps a row the socket added after the server built the refreshed page", async () => {
    for (const next of [null, "c1"]) {
      const name = freshDoc();
      serve({ newest: { activities: [c(1), c(2)], next } });
      const { timeline } = mountTimeline(name);
      await vi.waitFor(() => expect(timeline.loading.value).toBe(false));

      socket.emit("docinfo_update", socketComment(name, "C3", "late"));
      await timeline.reload();
      expect(keys(timeline)).toEqual(["comment:1", "comment:2", "comment:C3"]);
    }
  });

  it("does not join the held rows through a live row when more than a page arrived", async () => {
    const name = freshDoc();
    serve({ newest: { activities: [c(2), c(3)], next: "c2" } });
    const { timeline } = mountTimeline(name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));
    socket.emit("docinfo_update", socketComment(name, "C9", "live", "2026-01-09"));

    // comment:4 was never published and sits between the held rows and the new page
    const live = row("comment", "comment:C9", "2026-01-09");
    serve({
      newest: { activities: [c(5), c(6), live], next: "c5" },
      c5: { activities: [c(3), c(4)], next: "c3" },
    });
    await timeline.reload();
    expect(keys(timeline)).toEqual(["comment:5", "comment:6", "comment:C9"]);

    await timeline.paginate.fetchNextPage();
    expect(api.getDocumentPart.mock.lastCall?.[3]).toMatchObject({ before: "c5" });
    expect(keys(timeline)).toEqual(["comment:3", "comment:4", "comment:5", "comment:6", "comment:C9"]);
  });

  it("drops an older page that lands after a refresh moved the cursor", async () => {
    const name = freshDoc();
    let answer!: (page: Page) => void;
    serve({
      newest: { activities: [c(5), c(6)], next: "c5" },
      c5: new Promise<Page>((done) => (answer = done)),
    });
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.paginate.hasNextPage).toBe(true));
    const older = timeline.paginate.fetchNextPage();

    serve({ newest: { activities: [c(8), c(9)], next: "c8" } });
    await timeline.reload();
    answer({ activities: [c(3), c(4)], next: "c3" });
    await older;
    expect(keys(timeline)).toEqual(["comment:8", "comment:9"]);

    serve({ c8: { activities: [c(7)], next: null } });
    await timeline.paginate.fetchNextPage();
    expect(api.getDocumentPart.mock.lastCall?.[3]).toMatchObject({ before: "c8" });
  });

  it("clears the error once an older page reads", async () => {
    const name = freshDoc();
    serve({ newest: { activities: [c(2)], next: "c2" } });
    const timeline = useActivityTimeline("ToDo", name);
    await vi.waitFor(() => expect(timeline.paginate.hasNextPage).toBe(true));
    await timeline.paginate.fetchNextPage();
    expect(timeline.error.value).toBeInstanceOf(Error);

    serve({ c2: { activities: [c(1)], next: null } });
    await timeline.paginate.fetchNextPage();
    expect(timeline.error.value).toBeNull();
    expect(keys(timeline)).toEqual(["comment:1", "comment:2"]);
  });
});

describe("the prefetched read", () => {
  const newest = (key: string) => ({
    newest: { activities: [row("comment", key, "2026-01-01")], next: null },
  });

  it("is the first mount's page; a mount after every consumer left catches up", async () => {
    const name = freshDoc();
    serve(newest("comment:1"));
    await prefetchActivityTimeline("ToDo", name);

    vi.useFakeTimers();
    const first = mountTimeline(name);
    await vi.advanceTimersByTimeAsync(400);
    expect(api.getDocumentPart).toHaveBeenCalledTimes(1);
    expect(keys(first.timeline)).toEqual(["comment:1"]);

    mounted.splice(0).forEach((app) => app.unmount());
    serve(newest("comment:2"));
    const again = mountTimeline(name);
    await vi.waitFor(() => expect(keys(again.timeline)).toEqual(["comment:2"]));
    expect(api.getDocumentPart).toHaveBeenCalledTimes(2);
  });

  it("does not outlive the first paint: a mount after it catches up", async () => {
    const name = freshDoc();
    serve(newest("comment:1"));
    await prefetchActivityTimeline("ToDo", name);
    endActivityPrefetch("ToDo", name);

    serve(newest("comment:2"));
    const late = mountTimeline(name);
    await vi.waitFor(() => expect(keys(late.timeline)).toEqual(["comment:2"]));
    expect(api.getDocumentPart).toHaveBeenCalledTimes(2);
  });

  it("re-reads an idle store from an earlier visit before resolving, keeping its older rows", async () => {
    const name = freshDoc();
    serve({
      newest: { activities: [c(2), c(3)], next: "c2" },
      c2: { activities: [c(1)], next: null },
    });
    const visit = mountTimeline(name);
    await vi.waitFor(() => expect(visit.timeline.paginate.hasNextPage).toBe(true));
    await visit.timeline.paginate.fetchNextPage();
    mounted.splice(0).forEach((app) => app.unmount());

    let answer!: (page: Page) => void;
    serve({ newest: new Promise<Page>((done) => (answer = done)) });
    let landed = false;
    const prefetch = prefetchActivityTimeline("ToDo", name).then(() => (landed = true));
    await nextTick();
    expect(landed).toBe(false);
    expect(activityTimelineRows("ToDo", name).map((a) => a.key)).toEqual(["comment:1", "comment:2", "comment:3"]);

    answer({ activities: [c(3), c(4)], next: "c3" });
    await prefetch;
    const rows = ["comment:1", "comment:2", "comment:3", "comment:4"];
    expect(activityTimelineRows("ToDo", name).map((a) => a.key)).toEqual(rows);
    expect(api.getDocumentPart).toHaveBeenCalledTimes(3);
  });

  it("the re-read of an idle store is the first mount's page, not read again", async () => {
    const name = freshDoc();
    serve(newest("comment:1"));
    const visit = mountTimeline(name);
    await vi.waitFor(() => expect(keys(visit.timeline)).toEqual(["comment:1"]));
    mounted.splice(0).forEach((app) => app.unmount());

    serve(newest("comment:2"));
    await prefetchActivityTimeline("ToDo", name);
    vi.useFakeTimers();
    const again = mountTimeline(name);
    await vi.advanceTimersByTimeAsync(400);
    expect(keys(again.timeline)).toEqual(["comment:2"]);
    expect(api.getDocumentPart).toHaveBeenCalledTimes(2);
  });

  it("resolves at once for a store a mounted body keeps live", async () => {
    const name = freshDoc();
    serve(newest("comment:1"));
    const visit = mountTimeline(name);
    await vi.waitFor(() => expect(keys(visit.timeline)).toEqual(["comment:1"]));

    await prefetchActivityTimeline("ToDo", name);
    expect(api.getDocumentPart).toHaveBeenCalledTimes(1);
  });

  it("answers rows and a reload before any component mounts", async () => {
    const name = freshDoc();
    expect(activityTimelineRows("ToDo", name)).toEqual([]);
    serve(newest("comment:1"));
    await reloadActivityTimeline("ToDo", name);
    expect(activityTimelineRows("ToDo", name).map((a) => a.key)).toEqual(["comment:1"]);

    serve(newest("comment:2"));
    await reloadActivityTimeline("ToDo", name);
    expect(activityTimelineRows("ToDo", name).map((a) => a.key)).toEqual(["comment:2"]);
    expect(api.getDocumentPart).toHaveBeenCalledTimes(2);
  });
});

describe("pending rows", () => {
  const comment = (text: string) => ({
    type: "comment" as const,
    timestamp: "2026-01-05 10:00:00",
    author: { email: "a@x.com", fullname: "A" },
    data: { name: "", content: `<p>${text}</p>` },
  });

  it("swaps to the server key on resolve, and the socket add that follows changes nothing", async () => {
    const name = freshDoc();
    const { timeline, el } = mountTimeline(name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));

    const pending = addPendingActivity("ToDo", name, comment("hello"));
    const [draft] = timeline.activities.value;
    expect(draft.key).toMatch(/^pending:/);
    expect(draft.pending).toBe(true);
    await nextTick();
    const node = el.querySelector(".activity")!;
    expect(node.id).toBe(draft.key);

    pending.resolve("comment:C1", "2026-01-05 10:00:02");
    await nextTick();
    expect(timeline.activities.value).toMatchObject([
      { key: "comment:C1", timestamp: "2026-01-05 10:00:02", pending: false, renderKey: draft.key },
    ]);
    expect(el.querySelector(".activity")).toBe(node);
    expect(node.id).toBe("comment:C1");

    socket.emit("docinfo_update", socketComment(name, "C1", "hello"));
    await nextTick();
    expect(timeline.activities.value).toHaveLength(1);
    expect(timeline.activities.value[0]).toMatchObject({ key: "comment:C1", renderKey: draft.key });
    expect(timeline.activities.value[0].pending).toBeFalsy();
    expect(el.querySelectorAll(".activity")).toHaveLength(1);
    expect(el.querySelector(".activity")).toBe(node);
  });

  it("adopts the socket row when it beats the answer, and a late resolve adds nothing", async () => {
    const name = freshDoc();
    const { timeline } = mountTimeline(name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));

    const pending = addPendingActivity("ToDo", name, comment("first"));
    const draftKey = timeline.activities.value[0].key;
    socket.emit("docinfo_update", socketComment(name, "C2", "first"));
    pending.resolve("comment:C2");

    expect(timeline.activities.value).toHaveLength(1);
    expect(timeline.activities.value[0]).toMatchObject({ key: "comment:C2", renderKey: draftKey });
  });

  it("does not match a new pending row to an older row with the same text", async () => {
    const name = freshDoc();
    const old = row("comment", "comment:OLD", "2026-01-01", { name: "OLD", content: "<p>ok</p>" });
    serve({ newest: { activities: [old], next: null } });
    const { timeline } = mountTimeline(name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));

    addPendingActivity("ToDo", name, comment("ok"));
    const draftKey = timeline.activities.value[1].key;
    socket.emit("docinfo_update", socketComment(name, "HI", "hi"));
    expect(timeline.activities.value.find((a) => a.key === draftKey)?.pending).toBe(true);
    expect(timeline.activities.value[0]).not.toHaveProperty("renderKey");

    socket.emit("docinfo_update", socketComment(name, "NEW", "ok", "2026-01-05 10:00:03"));
    expect(timeline.activities.value.map((a) => a.key)).toEqual(["comment:OLD", "comment:HI", "comment:NEW"]);
    expect(timeline.activities.value[2]).toMatchObject({ renderKey: draftKey });
  });

  it("does not match a pending row to a same-text row an older page brings later", async () => {
    const name = freshDoc();
    const old = row("comment", "comment:OLD", "2026-01-01", { name: "OLD", content: "<p>ok</p>" });
    serve({
      newest: { activities: [c(5)], next: "c1" },
      c1: { activities: [old], next: null },
    });
    const { timeline } = mountTimeline(name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));

    addPendingActivity("ToDo", name, comment("ok"));
    const draftKey = timeline.activities.value[1].key;
    await timeline.paginate.fetchNextPage();
    expect(timeline.activities.value.find((a) => a.key === draftKey)?.pending).toBe(true);
    expect(timeline.activities.value[0]).not.toHaveProperty("renderKey");

    socket.emit("docinfo_update", socketComment(name, "NEW", "ok", "2026-01-05 10:00:03"));
    expect(keys(timeline)).toEqual(["comment:OLD", "comment:5", "comment:NEW"]);
    expect(timeline.activities.value[2]).toMatchObject({ renderKey: draftKey });
  });

  it("matches a comment echo that sorts before a future-dated email the feed held", async () => {
    const name = freshDoc();
    const email = row("email", "email:FUTURE", "2027-01-01 09:00:00", { name: "FUTURE", content: "<p>ok</p>" });
    serve({ newest: { activities: [c(1), email], next: null } });
    const { timeline } = mountTimeline(name);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));

    addPendingActivity("ToDo", name, comment("ok"));
    const draftKey = timeline.activities.value.find((a) => a.pending)!.key;
    socket.emit("docinfo_update", socketComment(name, "NEW", "ok", "2026-01-05 10:00:03"));
    expect(keys(timeline)).toEqual(["comment:1", "comment:NEW", "email:FUTURE"]);
    expect(timeline.activities.value[1]).toMatchObject({ renderKey: draftKey });
  });

  it("keeps a pending comment out of the emails view", async () => {
    const name = freshDoc();
    const emails = useActivityTimeline("ToDo", name, ["email"]);
    await vi.waitFor(() => expect(emails.loading.value).toBe(false));
    addPendingActivity("ToDo", name, comment("not an email"));
    expect(emails.activities.value).toEqual([]);
  });
});

describe("idle stores", () => {
  it("frees the least recently used idle store past twenty, never a mounted one", async () => {
    const kept = freshDoc();
    serve({ newest: { activities: [c(1)], next: null } });
    const { timeline } = mountTimeline(kept);
    await vi.waitFor(() => expect(timeline.loading.value).toBe(false));

    const evicted = freshDoc();
    serve({ newest: { activities: [row("comment", "comment:C1", "2026-01-05", { content: "<p>hi</p>" })], next: null } });
    await reloadActivityTimeline("ToDo", evicted);
    const draft = { type: "comment" as const, timestamp: "2026-01-05", data: { name: "", content: "<p>hi</p>" } };
    addPendingActivity("ToDo", evicted, draft).resolve("comment:C1");
    expect(activityTimelineRows("ToDo", evicted)[0]).toHaveProperty("renderKey");

    for (let i = 0; i < 20; i++) await reloadActivityTimeline("ToDo", freshDoc());
    expect(activityTimelineRows("ToDo", kept).map((a) => a.key)).toEqual(["comment:1"]);
    expect(activityTimelineRows("ToDo", evicted)).toEqual([]);

    await reloadActivityTimeline("ToDo", evicted);
    expect(activityTimelineRows("ToDo", evicted)[0]).not.toHaveProperty("renderKey");
  });

  it("goes live on a later mount when realtime was not ready at the first", async () => {
    const name = freshDoc();
    socket.ready = false;
    const first = mountTimeline(name);
    await vi.waitFor(() => expect(first.timeline.loading.value).toBe(false));
    mounted.splice(0).forEach((app) => app.unmount());

    socket.ready = true;
    const { timeline } = mountTimeline(name);
    await timeline.reload();
    socket.emit("docinfo_update", socketComment(name, "C1", "now live"));
    expect(keys(timeline)).toEqual(["comment:C1"]);
  });
});

describe("ActivityTimeline", () => {
  it("draws one loading row above the oldest row while the older page loads", async () => {
    const el = document.createElement("div");
    const app = createApp(() =>
      h(ActivityTimeline, {
        activities: [row("comment", "comment:1", "2026-01-01", { content: "<p>x</p>" })],
        paginate: { hasNextPage: true, isFetchingNextPage: true, fetchNextPage: () => {} },
      })
    );
    app.mount(el);
    mounted.push(app);
    await nextTick();
    const feed = el.querySelector(".activities")!;
    expect(feed.firstElementChild?.classList.contains("activity")).toBe(false);
    expect(feed.firstElementChild?.querySelector("svg")).not.toBeNull();
    expect(feed.querySelectorAll("button")).toHaveLength(0);
  });

  it("scrolls to the run a folded version row draws in", async () => {
    const change = (key: string, at: string) =>
      row("version", key, at, { fieldname: "status", type: "diff", prefix: "changed status", from: "a", to: "b" });
    const timeline = ref<any>(null);
    const el = document.createElement("div");
    const app = createApp(() =>
      h(ActivityTimeline, {
        ref: timeline,
        activities: [change("version:V1-0", "2026-01-01 10:00:00"), change("version:V2-0", "2026-01-01 10:05:00")],
      })
    );
    app.mount(el);
    mounted.push(app);
    await nextTick();
    const exposed = timeline.value;
    Element.prototype.scrollIntoView ??= () => {};

    expect(exposed.scrollToRow("version:V2-0")).toBe(true);
    expect(el.querySelector('[id="version:V1-0"]')!.classList.contains("timeline-row-flash")).toBe(true);
    expect(exposed.scrollToRow("comment:gone")).toBe(false);
  });
});
