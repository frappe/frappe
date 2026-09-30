// Where a record's view is kept: the history entry for Back and Forward, and per record while its complete entry stays.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearDataCache, feedRecordRead, RECORD_PARTS, settleTicket, takeTicket } from "@framework/ui/cache";
import { recallView, resetViewMemory, viewKeeper, type RecordView } from "../viewMemory";

function view(tab: string): RecordView {
  return { tab, formTab: "", sections: {}, panel: {}, offsets: { columns: {} } };
}

/** A record read with every part, as the record page makes one: its entry is complete. */
function readRecord(name: string) {
  const ticket = takeTicket();
  const parts = Object.fromEntries(RECORD_PARTS.map((part) => [part, part === "follows" ? false : []]));
  feedRecordRead(ticket, "Note", { data: { doctype: "Note", name, modified: "2026-09-25" }, ...parts } as never, [
    ...RECORD_PARTS,
  ]);
  settleTicket(ticket);
}

let position = 100;

/** A new history entry, numbered as vue-router numbers one. */
function pushEntry() {
  history.pushState({ position: ++position }, "");
}

beforeEach(() => {
  pushEntry();
  readRecord("N-1");
});

afterEach(() => {
  vi.restoreAllMocks();
  clearDataCache();
  resetViewMemory();
});

describe("recallView", () => {
  it("takes the history entry's view over the record's own", () => {
    const keeper = viewKeeper("Note", "N-1");
    keeper(view("activity"));
    pushEntry();
    viewKeeper("Note", "N-1")(view("files"));
    history.back();

    expect(recallView("Note", "N-1", false)?.tab).toBe("activity");
  });

  it("takes the record's own view on a return with no view in the history entry", () => {
    viewKeeper("Note", "N-1")(view("activity"));
    pushEntry();

    expect(recallView("Note", "N-1", false)?.tab).toBe("activity");
  });

  it("gives nothing on a new navigation with no view in the history entry", () => {
    viewKeeper("Note", "N-1")(view("activity"));
    pushEntry();

    expect(recallView("Note", "N-1", true)).toBeNull();
  });

  it("still takes the history entry's view on a new navigation, as Back to a `?tab=` address is", () => {
    viewKeeper("Note", "N-1")(view("activity"));

    expect(recallView("Note", "N-1", true)?.tab).toBe("activity");
  });

  it("ignores a history entry that holds another record's view", () => {
    readRecord("N-2");
    viewKeeper("Note", "N-2")(view("files"));

    expect(recallView("Note", "N-1", false)).toBeNull();
  });
});

describe("the per-record store", () => {
  it("is dropped when the record's complete entry leaves the cache", () => {
    viewKeeper("Note", "N-1")(view("activity"));
    pushEntry();

    clearDataCache();

    expect(recallView("Note", "N-1", false)).toBeNull();
  });

  it("takes no view while the record's entry is not complete", () => {
    viewKeeper("Note", "N-3")(view("activity"));
    pushEntry();

    expect(recallView("Note", "N-3", false)).toBeNull();
  });
});

describe("viewKeeper", () => {
  it("writes nothing into a history entry other than the one the page opened on", () => {
    const keeper = viewKeeper("Note", "N-1");
    pushEntry();

    keeper(view("activity"));

    expect((history.state as { recordView?: unknown }).recordView).toBeUndefined();
    history.back();
    expect((history.state as { recordView?: unknown }).recordView).toBeUndefined();
  });

  it("still keeps the record's own view after the history entry changed", () => {
    const keeper = viewKeeper("Note", "N-1");
    pushEntry();

    keeper(view("activity"));

    expect(recallView("Note", "N-1", false)?.tab).toBe("activity");
  });

  it("writes the history entry again only when the view changed", () => {
    const keeper = viewKeeper("Note", "N-1");
    const writes = vi.spyOn(history, "replaceState");

    keeper(view("details"));
    keeper(view("details"));
    keeper(view("files"));

    expect(writes).toHaveBeenCalledTimes(2);
  });

  it("keeps the record's own copy when the browser refuses the history write, and tries again", () => {
    const keeper = viewKeeper("Note", "N-1");
    vi.spyOn(history, "replaceState").mockImplementation(() => {
      throw new DOMException("too many calls", "SecurityError");
    });
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    expect(() => keeper(view("activity"))).not.toThrow();
    expect(warn).toHaveBeenCalledOnce();
    expect(recallView("Note", "N-1", false)?.tab).toBe("activity");

    vi.mocked(history.replaceState).mockRestore();
    keeper(view("activity"));

    expect((history.state as { recordView: { view: RecordView } }).recordView.view.tab).toBe("activity");
  });
});
