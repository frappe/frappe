import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import ActivityTimeline from "../ActivityTimeline.vue";
import type { Activity, Pagination } from "../types";

// Deprecated paging API, kept for hosts built on develop: `loadMore.position: "inline"` and
// `Pagination.isPagedRow` put the Load More row inside the feed, above the oldest paged row.
const mounted: ReturnType<typeof createApp>[] = [];
afterEach(() => {
  for (const app of mounted.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

const log = (key: string, timestamp: string): Activity =>
  ({ type: "log", key, timestamp, data: { subtype: "edited", text: key } }) as unknown as Activity;
const email = (key: string, timestamp: string): Activity =>
  ({ type: "email", key, timestamp, data: { name: key, subject: key, content: "" } }) as unknown as Activity;

async function mountTimeline(activities: Activity[], paginate: Partial<Pagination>) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp({
    render: () =>
      h(
        ActivityTimeline,
        {
          activities,
          paginate: { hasNextPage: true, isFetchingNextPage: false, fetchNextPage: () => {}, ...paginate },
        },
        {
          "icon-log": () => h("i"),
          "icon-email": () => h("i"),
          "item-log": () => h("i"),
          "item-email": () => h("i"),
        }
      ),
  });
  app.mount(root);
  mounted.push(app);
  await nextTick();
  return root;
}

const order = (root: HTMLElement) =>
  Array.from(root.querySelectorAll(".activity")).map((row) => row.querySelector("[data-type]")?.getAttribute("data-type"));

describe("ActivityTimeline inline Load More (deprecated)", () => {
  const feed = [log("a", "2026-01-01 10:00:00"), email("e1", "2026-01-02 10:00:00"), log("b", "2026-01-03 10:00:00")];

  it("puts a load_more row above the oldest email row", async () => {
    const root = await mountTimeline(feed, { loadMore: { position: "inline" } });
    expect(order(root)).toEqual(["log", "load_more", "email", "log"]);
    expect(root.querySelectorAll("button")).toHaveLength(1);
  });

  it("asks the host's isPagedRow which row the next page extends", async () => {
    const isPagedRow = vi.fn((row) => row.key === "b");
    const root = await mountTimeline(feed, { loadMore: { position: "inline" }, isPagedRow });
    expect(order(root)).toEqual(["log", "email", "load_more", "log"]);
  });

  it("loads the next page from the inline row", async () => {
    const fetchNextPage = vi.fn();
    const root = await mountTimeline(feed, { loadMore: { position: "inline" }, fetchNextPage });
    root.querySelector("button")!.click();
    expect(fetchNextPage).toHaveBeenCalledOnce();
  });

  it("adds no row with no next page, and keeps the top button for position top", async () => {
    expect(order(await mountTimeline(feed, { loadMore: { position: "inline" }, hasNextPage: false }))).toEqual([
      "log",
      "email",
      "log",
    ]);
    const top = await mountTimeline(feed, { loadMore: { position: "top" } });
    expect(order(top)).toEqual(["log", "email", "log"]);
    expect(top.querySelectorAll("button")).toHaveLength(1);
  });
});
