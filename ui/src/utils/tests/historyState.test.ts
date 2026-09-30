// One key written into the history entry.
import { afterEach, describe, expect, it, vi } from "vitest";
import { keepInHistory } from "../historyState";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("keepInHistory", () => {
  it("writes its key over the entry's other keys", () => {
    history.replaceState({ position: 7, list: { scrollTop: 40 } }, "");

    expect(keepInHistory("recordView", { tab: "files" })).toBe(true);

    expect(history.state).toEqual({ position: 7, list: { scrollTop: 40 }, recordView: { tab: "files" } });
  });

  it("returns false, with a warning, when the browser refuses the write", () => {
    vi.spyOn(history, "replaceState").mockImplementation(() => {
      throw new DOMException("too many calls", "SecurityError");
    });
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    expect(keepInHistory("list", { scrollTop: 40 })).toBe(false);
    expect(warn).toHaveBeenCalledOnce();
  });
});
