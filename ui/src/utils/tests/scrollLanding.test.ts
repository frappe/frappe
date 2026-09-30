// A scroll reported once it settles, and one key written into the history entry.
import { afterEach, describe, expect, it, vi } from "vitest";
import { keepInHistory, onScrollSettled } from "../scrollLanding";

const stops: (() => void)[] = [];

afterEach(() => {
  for (const stop of stops.splice(0)) stop();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

/** A box with another box inside it, both in the page. */
function boxes() {
  const outer = document.createElement("div");
  const inner = document.createElement("div");
  outer.appendChild(inner);
  document.body.appendChild(outer);
  return { outer, inner };
}

function watch(element: HTMLElement) {
  const settled = vi.fn();
  const stop = onScrollSettled(element, settled);
  stops.push(stop);
  return { settled, stop };
}

/** Takes `onscrollend` off the window, as a browser without the event has it. */
function withoutScrollEnd() {
  let owner: object | null = window;
  while (owner && !Object.prototype.hasOwnProperty.call(owner, "onscrollend")) owner = Object.getPrototypeOf(owner);
  if (!owner) return;
  const found = owner;
  const descriptor = Object.getOwnPropertyDescriptor(found, "onscrollend")!;
  delete (found as Record<string, unknown>).onscrollend;
  stops.push(() => Object.defineProperty(found, "onscrollend", descriptor));
}

describe("onScrollSettled", () => {
  it("calls once per scroll gesture, at its scrollend", () => {
    const { outer } = boxes();
    const { settled } = watch(outer);

    for (let frame = 0; frame < 5; frame++) outer.dispatchEvent(new Event("scroll"));
    expect(settled).not.toHaveBeenCalled();

    outer.dispatchEvent(new Event("scrollend"));
    outer.dispatchEvent(new Event("scrollend"));

    expect(settled).toHaveBeenCalledTimes(2);
  });

  it("hears a box inside the element settle, though scrollend does not bubble", () => {
    const { outer, inner } = boxes();
    const { settled } = watch(outer);

    inner.dispatchEvent(new Event("scrollend"));

    expect(settled).toHaveBeenCalledOnce();
  });

  it("calls nothing once stopped", () => {
    const { outer } = boxes();
    const { settled, stop } = watch(outer);

    stop();
    outer.dispatchEvent(new Event("scrollend"));

    expect(settled).not.toHaveBeenCalled();
  });

  it("calls once per frame on scroll where the browser has no scrollend", async () => {
    withoutScrollEnd();
    expect("onscrollend" in window).toBe(false);
    const { outer, inner } = boxes();
    const { settled } = watch(outer);

    outer.dispatchEvent(new Event("scroll"));
    inner.dispatchEvent(new Event("scroll"));
    await new Promise((resolve) => requestAnimationFrame(resolve));

    expect(settled).toHaveBeenCalledOnce();
  });
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
