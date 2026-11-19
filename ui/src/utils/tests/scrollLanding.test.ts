// A scroll reported once it settles.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { onScrollSettled } from "../scrollLanding";

const stops: (() => void)[] = [];

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  for (const stop of stops.splice(0)) stop();
  vi.useRealTimers();
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

describe("onScrollSettled", () => {
  it("calls once, 150 ms after the last of several scrolls, and not before", () => {
    const { outer } = boxes();
    const { settled } = watch(outer);

    for (let event = 0; event < 3; event++) {
      outer.dispatchEvent(new Event("scroll"));
      vi.advanceTimersByTime(100);
    }
    vi.advanceTimersByTime(49);
    expect(settled).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(settled).toHaveBeenCalledOnce();
  });

  it("hears a box inside the element scroll, though scroll does not bubble", () => {
    const { outer, inner } = boxes();
    const { settled } = watch(outer);

    inner.dispatchEvent(new Event("scroll"));
    vi.advanceTimersByTime(150);

    expect(settled).toHaveBeenCalledOnce();
  });

  it("drops a pending call once stopped", () => {
    const { outer } = boxes();
    const { settled, stop } = watch(outer);

    outer.dispatchEvent(new Event("scroll"));
    stop();
    vi.advanceTimersByTime(150);

    expect(settled).not.toHaveBeenCalled();
  });
});
