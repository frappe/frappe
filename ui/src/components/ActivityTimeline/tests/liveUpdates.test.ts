import { describe, expect, it, vi } from "vitest";
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
vi.mock("../utils", () => ({
  getAssignee: () => undefined,
  stripHtml: (html: string) => html,
}));

const { createLiveUpdates } = await import("../liveUpdates");
const { addPendingActivity } = await import("../pendingRows");

let ticket = 0;

/** A ticket with your comment still saving, and a refetch that returns `feedAfterRefetch`. */
function holdingTicket(feedAfterRefetch: () => Activity[]) {
  const docname = String(++ticket);
  const resource = { data: [] as Activity[], fetched: true };
  let settleRefresh = () => {};
  const refresh = () =>
    new Promise<void>((resolve) => {
      settleRefresh = () => {
        resource.data = feedAfterRefetch();
        resolve();
      };
    });
  createLiveUpdates("HD Ticket", docname, resource as never, undefined, refresh)();
  addPendingActivity("HD Ticket", docname, {
    type: "comment",
    timestamp: "2026-09-28 12:00:00",
    data: { name: "", content: "mine" },
  } as never);

  const send = (action: string, name: string) =>
    handlers.docinfo_update({
      action,
      key: "comments",
      doc: { name, reference_doctype: "HD Ticket", reference_name: docname, creation: "" },
    });
  const keys = () => resource.data.map((a) => a.key);
  const refetch = async () => {
    settleRefresh();
    await Promise.resolve();
  };
  return { send, keys, refetch };
}

describe("live rows held back while your comment saves", () => {
  it("are not drawn until the refetch lands", async () => {
    const t = holdingTicket(() => [{ key: "comment:theirs" } as Activity]);
    t.send("add", "theirs");
    expect(t.keys()).toEqual([]);
    await t.refetch();
    expect(t.keys()).toEqual(["comment:theirs"]);
  });

  it("come back when the refetch leaves them out", async () => {
    // a failed fetch, or an email dated older than the first page
    const t = holdingTicket(() => []);
    t.send("add", "theirs");
    await t.refetch();
    expect(t.keys()).toEqual(["comment:theirs"]);
  });

  it("stay gone when deleted before the refetch lands", async () => {
    const t = holdingTicket(() => []);
    t.send("add", "theirs");
    t.send("delete", "theirs");
    await t.refetch();
    expect(t.keys()).toEqual([]);
  });
});
