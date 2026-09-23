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
  return { instance: { on, off }, emit };
});
// Through the frontend's link: from inside ui/, frappe-ui resolves nowhere.
vi.mock("../../../../../frontend/node_modules/@framework/ui/src/api", () => ({ getDocumentPart: api.getDocumentPart }));
vi.mock("../../../../../frontend/node_modules/@framework/ui/src/socket", () => ({
  getSocketInstance: () => socket.instance,
  subscribeToDoc: () => () => {},
}));

import {
  activityTimelineRows,
  endActivityPrefetch,
  prefetchActivityTimeline,
  reloadActivityTimeline,
  useActivityTimeline,
} from "../../../../../frontend/node_modules/@framework/ui/src/components/ActivityTimeline/useActivityTimeline";
import { addPendingActivity } from "../../../../../frontend/node_modules/@framework/ui/src/components/ActivityTimeline/pendingRows";
import ActivityTimeline from "../../../../../frontend/node_modules/@framework/ui/src/components/ActivityTimeline/ActivityTimeline.vue";

let docCounter = 0;
/** A fresh document per test: the composable keeps one store per document for the session. */
function freshDoc() {
  return `T-${docCounter++}`;
}

function row(type: Activity["type"], key: string, timestamp: string, data = {}): Activity {
  return { type, key, timestamp, author: { email: "a@x.com", fullname: "A" }, data } as Activity;
}

type Page = { activities: Activity[]; next: string | null };

/** Answers each read by its `before` cursor; the newest page sits under "newest". */
function serve(pages: Record<string, Page>) {
  api.getDocumentPart.mockImplementation(async (_dt, _name, _part, params) => {
    const page = pages[params.before ?? "newest"];
    if (!page) throw new Error(`no page for ${params.before}`);
    return { data: page };
  });
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
  api.getDocumentPart.mockReset();
  serve({ newest: { activities: [], next: null } });
});

afterEach(() => {
  mounted.splice(0).forEach((app) => app.unmount());
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
    const c = (n: number) => row("comment", `comment:${n}`, `2026-01-0${n}`);
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
    const c = (n: number) => row("comment", `comment:${n}`, `2026-01-0${n}`);
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
});

describe("the prefetched read", () => {
  const newest = (key: string) => ({
    newest: { activities: [row("comment", key, "2026-01-01")], next: null },
  });

  it("is the first mount's page; a mount after every consumer left catches up", async () => {
    const name = freshDoc();
    serve(newest("comment:1"));
    await prefetchActivityTimeline("ToDo", name);

    const first = mountTimeline(name);
    await new Promise((done) => setTimeout(done, 400));
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
  const socketComment = (docname: string, name: string, text: string) => ({
    key: "comments",
    action: "add",
    doc: {
      name,
      reference_doctype: "ToDo",
      reference_name: docname,
      content: `<p>${text}</p>`,
      creation: "2026-01-05 10:00:02",
      owner: "a@x.com",
    },
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

  it("keeps a pending comment out of the emails view", async () => {
    const name = freshDoc();
    const emails = useActivityTimeline("ToDo", name, ["email"]);
    await vi.waitFor(() => expect(emails.loading.value).toBe(false));
    addPendingActivity("ToDo", name, comment("not an email"));
    expect(emails.activities.value).toEqual([]);
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
