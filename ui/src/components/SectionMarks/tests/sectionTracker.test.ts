import { describe, expect, it } from "vitest";
import { sectionsInView } from "../sectionTracker";

const edges = (...spans: [number, number][]) =>
  spans.map(([top, bottom], index) => ({ key: `s${index}`, top, bottom }));

describe("sectionsInView", () => {
  it("holds each section that shows in the viewport, in part or whole", () => {
    expect([...sectionsInView(edges([-300, 20], [20, 400], [400, 900]), 600)]).toEqual([
      "s0",
      "s1",
      "s2",
    ]);
  });

  it("leaves out sections above or below the viewport", () => {
    expect([...sectionsInView(edges([-500, -10], [-10, 300], [600, 900]), 600)]).toEqual(["s1"]);
  });

  it("leaves out a section that only touches an edge", () => {
    expect([...sectionsInView(edges([-200, 0], [0, 600], [600, 700]), 600)]).toEqual(["s1"]);
  });

  it("is empty when no section is on the page", () => {
    expect(sectionsInView([], 600).size).toBe(0);
  });
});
