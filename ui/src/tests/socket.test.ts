import { describe, expect, it, vi } from "vitest";
import type { RealtimeSocket } from "../socket";

// The room table is module state, so a test that reused the import would inherit
// the previous test's holders. Re-importing after `resetModules()` is what gives
// each test an empty table.
async function loadSocket() {
  vi.resetModules();
  return import("../socket");
}

function fakeSocket() {
  const emitted: unknown[][] = [];
  const socket: RealtimeSocket = {
    emit: (event, ...args) => {
      emitted.push([event, ...args]);
    },
    on: () => {},
    off: () => {},
  };
  return { socket, emitted };
}

describe("subscribeToDoc", () => {
  it("joins the room for the first holder", async () => {
    const { subscribeToDoc } = await loadSocket();
    const { socket, emitted } = fakeSocket();

    subscribeToDoc(socket, "ToDo", "T1");

    expect(emitted).toEqual([["doc_subscribe", "ToDo", "T1"]]);
  });

  it("does not join again for a second holder of the same document", async () => {
    const { subscribeToDoc } = await loadSocket();
    const { socket, emitted } = fakeSocket();

    subscribeToDoc(socket, "ToDo", "T1");
    subscribeToDoc(socket, "ToDo", "T1");

    expect(emitted).toEqual([["doc_subscribe", "ToDo", "T1"]]);
  });

  it("leaves only once the last holder has released", async () => {
    const { subscribeToDoc } = await loadSocket();
    const { socket, emitted } = fakeSocket();

    const releaseA = subscribeToDoc(socket, "ToDo", "T1");
    const releaseB = subscribeToDoc(socket, "ToDo", "T1");

    releaseA();
    expect(emitted).toEqual([["doc_subscribe", "ToDo", "T1"]]); // B still holds it

    releaseB();
    expect(emitted).toEqual([
      ["doc_subscribe", "ToDo", "T1"],
      ["doc_unsubscribe", "ToDo", "T1"],
    ]);
  });

  it("ignores a release that already ran, so it cannot drop another holder", async () => {
    const { subscribeToDoc } = await loadSocket();
    const { socket, emitted } = fakeSocket();

    const releaseA = subscribeToDoc(socket, "ToDo", "T1");
    const releaseB = subscribeToDoc(socket, "ToDo", "T1");

    releaseA();
    releaseA(); // a double unmount must not evict B

    expect(emitted).toEqual([["doc_subscribe", "ToDo", "T1"]]);

    releaseB();
    expect(emitted).toEqual([
      ["doc_subscribe", "ToDo", "T1"],
      ["doc_unsubscribe", "ToDo", "T1"],
    ]);
  });

  it("joins afresh after the room was fully released", async () => {
    const { subscribeToDoc } = await loadSocket();
    const { socket, emitted } = fakeSocket();

    subscribeToDoc(socket, "ToDo", "T1")();
    subscribeToDoc(socket, "ToDo", "T1");

    expect(emitted).toEqual([
      ["doc_subscribe", "ToDo", "T1"],
      ["doc_unsubscribe", "ToDo", "T1"],
      ["doc_subscribe", "ToDo", "T1"],
    ]);
  });

  it("counts each document separately", async () => {
    const { subscribeToDoc } = await loadSocket();
    const { socket, emitted } = fakeSocket();

    const releaseTodo = subscribeToDoc(socket, "ToDo", "T1");
    subscribeToDoc(socket, "Note", "N1");
    releaseTodo();

    expect(emitted).toEqual([
      ["doc_subscribe", "ToDo", "T1"],
      ["doc_subscribe", "Note", "N1"],
      ["doc_unsubscribe", "ToDo", "T1"], // Note is untouched
    ]);
  });

  it("returns a harmless release when there is no socket", async () => {
    const { subscribeToDoc, resubscribeHeldDocs } = await loadSocket();
    const { socket, emitted } = fakeSocket();

    expect(() => subscribeToDoc(undefined, "ToDo", "T1")()).not.toThrow();

    resubscribeHeldDocs(socket);
    expect(emitted).toEqual([]); // nothing was ever held
  });
});

describe("resubscribeHeldDocs", () => {
  it("re-joins every room still held", async () => {
    const { subscribeToDoc, resubscribeHeldDocs } = await loadSocket();
    const { socket, emitted } = fakeSocket();

    subscribeToDoc(socket, "ToDo", "T1");
    const releaseNote = subscribeToDoc(socket, "Note", "N1");
    releaseNote();
    emitted.length = 0;

    resubscribeHeldDocs(socket);

    expect(emitted).toEqual([["doc_subscribe", "ToDo", "T1"]]); // Note was released
  });

  it("emits nothing when no socket is available", async () => {
    const { subscribeToDoc, resubscribeHeldDocs } = await loadSocket();
    const { socket, emitted } = fakeSocket();

    subscribeToDoc(socket, "ToDo", "T1");
    emitted.length = 0;

    resubscribeHeldDocs(undefined);

    expect(emitted).toEqual([]);
  });
});
