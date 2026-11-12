import { describe, expect, it } from "vitest";
import { clampBarLeft, keepBarInBox } from "../bubbleLimiter";

describe("clampBarLeft", () => {
  it("keeps a centred bar that has room", () => {
    expect(clampBarLeft(1230, 180, 1215, 1425)).toBe(1230);
  });

  it("moves a bar that hangs left of the box to the box's left edge", () => {
    expect(clampBarLeft(1150, 180, 1215, 1425)).toBe(1215);
  });

  it("moves a bar that hangs right of the box back inside it", () => {
    expect(clampBarLeft(1300, 180, 1215, 1425)).toBe(1245);
  });

  it("lets the right edge win when the bar is wider than the box", () => {
    expect(clampBarLeft(1118, 243, 1215, 1425)).toBe(1182);
  });
});

describe("keepBarInBox", () => {
  // A box from 1215 to 1425.
  const box = () =>
    ({ getBoundingClientRect: () => ({ left: 1215, right: 1425 }) }) as unknown as HTMLElement;

  // Floating UI's coordinates may be offset from the viewport's; the limiter keeps that offset.
  const state = (x: number, width: number, offset = 0) => ({
    x,
    y: 40,
    rects: { reference: { x: 1220 - offset }, floating: { width } },
    elements: { reference: { getBoundingClientRect: () => ({ left: 1220 }) } },
  });

  it("starts the bar at the box's left edge in the limiter's own coordinates", () => {
    expect(keepBarInBox(box).fn(state(1150, 180))).toEqual({ x: 1215, y: 40 });
    expect(keepBarInBox(box).fn(state(1150 - 100, 180, 100))).toEqual({ x: 1115, y: 40 });
  });

  it("keeps a centred bar where it is when it fits", () => {
    expect(keepBarInBox(box).fn(state(1230, 180))).toEqual({ x: 1230, y: 40 });
  });

  it("keeps the bar inside the box on the right", () => {
    expect(keepBarInBox(box).fn(state(1300, 180)).x).toBe(1425 - 180);
  });

  it("leaves the bar alone before the box is drawn", () => {
    expect(keepBarInBox(() => null).fn(state(1118, 243))).toEqual({ x: 1118, y: 40 });
  });
});
