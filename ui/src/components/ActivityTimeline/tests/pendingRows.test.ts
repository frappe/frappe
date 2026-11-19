import { describe, expect, it } from "vitest";
import { ref } from "vue";
import type { Activity } from "../types";
import { addPendingActivity, docKey, trackPendingRows, withPendingRows } from "../pendingRows";

let ticket = 0;

const comment = (key: string): Activity =>
  ({ type: "comment", key, timestamp: "2026-09-28 12:00:00", data: {} }) as Activity;

/** A ticket whose feed is tracked, with your comment still saving. */
function savingTicket() {
  const docname = String(++ticket);
  const doc = docKey("HD Ticket", docname);
  const feed = ref<Activity[]>([]);
  trackPendingRows(doc, feed);
  const row = addPendingActivity("HD Ticket", docname, {
    type: "comment",
    timestamp: "2026-09-28 12:00:00",
    data: { name: "", content: "hi" },
  } as Parameters<typeof addPendingActivity>[2]);
  const drawn = () => withPendingRows(doc, feed.value, undefined);
  return { feed, row, drawn };
}

describe("pending rows", () => {
  it("retires when the feed has the row before the key lands", () => {
    const { feed, row, drawn } = savingTicket();
    const pendingKey = drawn()[0].key;

    // the echo came first and says nothing to match on, so nothing retires
    feed.value = [comment("comment:abc")];
    expect(drawn().filter((a) => a.pending)).toHaveLength(1);

    row.resolve("comment:abc");
    expect(drawn()).toMatchObject([{ key: "comment:abc", renderKey: pendingKey }]);
  });

  it("never retires on a different row that looks the same", () => {
    const { feed, row, drawn } = savingTicket();
    row.resolve("comment:mine");
    feed.value = [comment("comment:theirs")];
    expect(drawn().map((a) => a.key)).toEqual(["comment:theirs", "comment:mine"]);
  });

  it("drops a row whose request failed", () => {
    const { row, drawn } = savingTicket();
    row.drop();
    expect(drawn()).toHaveLength(0);
  });
});
