import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { Activity } from "../types";

const handlers: Record<string, (payload: unknown) => void> = {};
vi.mock("../../../socket", () => ({
  getSocketInstance: () => ({
    on: (event: string, handler: (payload: unknown) => void) => {
      handlers[event] = handler;
    },
    off: () => {},
  }),
  subscribeToDoc: () => () => {},
}));

const { createLiveUpdates } = await import("../liveUpdates");

describe("a live edit", () => {
  it("keeps the author the feed already drew, avatar included", () => {
    const author = { email: "a@x.com", fullname: "A", image: "/a.png" };
    const original = {
      type: "comment",
      key: "comment:C1",
      timestamp: "2026-09-28 12:00:00",
      author,
      data: { name: "C1", content: "<p>hi</p>" },
    } as Activity;
    const feed = { data: ref([original]), fetched: ref(true), prefetched: ref(true) };
    createLiveUpdates("HD Ticket", "1", feed, undefined, () => Promise.resolve())();

    handlers.docinfo_update({
      action: "update",
      key: "comments",
      doc: {
        name: "C1",
        reference_doctype: "HD Ticket",
        reference_name: "1",
        content: "<p>edited</p>",
        creation: "2026-09-28 12:00:00",
        owner: "b@x.com",
      },
    });

    expect(feed.data.value).toMatchObject([
      { key: "comment:C1", author, data: { content: "<p>edited</p>" } },
    ]);
  });
});
