import { describe, expect, it } from "vitest";
import type { Activity } from "../types";
import {
  addPendingActivity,
  hasUnresolvedRowOfType,
  pendingRowsFor,
  retirePendingRows,
  withAdoptedKeys,
} from "../pendingRows";

let ticket = 0;
const newTicket = () => String(++ticket);

const comment = (key: string): Activity =>
  ({ type: "comment", key, timestamp: "2026-09-28 12:00:00", data: {} }) as Activity;

const addComment = (docname: string) =>
  addPendingActivity("HD Ticket", docname, {
    type: "comment",
    timestamp: "2026-09-28 12:00:00",
    data: { name: "", content: "hi" },
  } as Parameters<typeof addPendingActivity>[2]);

describe("pending rows", () => {
  it("holds back live rows of its type only until the key lands", () => {
    const docname = newTicket();
    const row = addComment(docname);
    expect(hasUnresolvedRowOfType("HD Ticket", docname, "comment")).toBe(true);
    expect(hasUnresolvedRowOfType("HD Ticket", docname, "email")).toBe(false);

    row.resolve("comment:abc");
    expect(hasUnresolvedRowOfType("HD Ticket", docname, "comment")).toBe(false);
  });

  it("retires when the feed has the row before the key lands", () => {
    const docname = newTicket();
    const row = addComment(docname);
    const pendingKey = pendingRowsFor("HD Ticket", docname)[0].key;
    const feed = [comment("comment:abc")];

    // the echo came first: without the key there is no match, so nothing retires
    retirePendingRows("HD Ticket", docname, feed);
    expect(pendingRowsFor("HD Ticket", docname)).toHaveLength(1);

    row.resolve("comment:abc");
    retirePendingRows("HD Ticket", docname, feed);
    expect(pendingRowsFor("HD Ticket", docname)).toHaveLength(0);
    expect(withAdoptedKeys("HD Ticket", docname, feed)[0].key).toBe(pendingKey);
  });

  it("never retires on a different row that looks the same", () => {
    const docname = newTicket();
    addComment(docname).resolve("comment:mine");
    retirePendingRows("HD Ticket", docname, [comment("comment:theirs")]);
    expect(pendingRowsFor("HD Ticket", docname)).toHaveLength(1);
  });

  it("drops a row whose request failed", () => {
    const docname = newTicket();
    addComment(docname).drop();
    expect(pendingRowsFor("HD Ticket", docname)).toHaveLength(0);
    expect(hasUnresolvedRowOfType("HD Ticket", docname, "comment")).toBe(false);
  });
});
