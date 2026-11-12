import { afterEach, describe, expect, it } from "vitest";
import { clampBarLeft, keepBarInBox } from "../bubbleLimiter";

describe("clampBarLeft", () => {
  it("keeps a centred bar that has room", () => {
    expect(clampBarLeft(1250, 120, 1215, 1440)).toBe(1250);
  });

  it("moves a bar that hangs left of the box to the box's left edge", () => {
    expect(clampBarLeft(1150, 120, 1215, 1440)).toBe(1215);
  });

  it("lets the right edge win when the bar is wider than the room after the box's left edge", () => {
    expect(clampBarLeft(1118, 243, 1215, 1440)).toBe(1197);
  });
});

describe("keepBarInBox", () => {
  afterEach(() => {
    document.body.innerHTML = "";
    delete (document.documentElement as { clientWidth?: number }).clientWidth;
  });

  // A box at 1215 in a panel whose right edge is at `panelRight`, in a viewport `viewport` wide.
  function mount(panelRight = 1425, viewport = 1500) {
    Object.defineProperty(document.documentElement, "clientWidth", {
      value: viewport,
      configurable: true,
    });
    const panel = document.createElement("div");
    panel.setAttribute("data-picker-bound", "");
    const box = document.createElement("div");
    panel.append(box);
    document.body.append(panel);
    panel.getBoundingClientRect = () => ({ right: panelRight }) as DOMRect;
    box.getBoundingClientRect = () => ({ left: 1215 }) as DOMRect;
    return box;
  }

  // Floating UI's coordinates may be offset from the viewport's; the limiter keeps that offset.
  const state = (x: number, width: number, offset = 0) => ({
    x,
    y: 40,
    rects: { reference: { x: 1220 - offset }, floating: { width } },
    elements: { reference: { getBoundingClientRect: () => ({ left: 1220 }) } },
  });

  it("starts the bar at the box's left edge in the limiter's own coordinates", () => {
    const box = mount();
    expect(keepBarInBox(() => box).fn(state(1150, 120))).toEqual({ x: 1215, y: 40 });
    expect(keepBarInBox(() => box).fn(state(1150 - 100, 120, 100))).toEqual({ x: 1115, y: 40 });
  });

  it("keeps a wide bar inside the panel on the right", () => {
    const box = mount(1425, 1500);
    expect(keepBarInBox(() => box).fn(state(1118, 243)).x).toBe(1425 - 243);
  });

  it("keeps a wide bar inside the viewport when the panel runs past it", () => {
    const box = mount(1441, 1440);
    expect(keepBarInBox(() => box).fn(state(1118, 243)).x).toBe(1440 - 243);
  });

  it("leaves the bar alone before the box is drawn", () => {
    expect(keepBarInBox(() => null).fn(state(1118, 243))).toEqual({ x: 1118, y: 40 });
  });
});
