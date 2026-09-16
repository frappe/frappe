// The body surface: two built-in columns that any verb may move or hide, the columns a
// script adds around them, and the row's maths — flex share, edge side, drop order.
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  BodySurface,
  FLEX_MIN_WIDTH,
  SCRIPT_COLUMN_DEFAULTS,
  STRIP_WIDTH,
  columnBounds,
  dragOutcome,
  projectBody,
  type Remembered,
} from "../body";
import type { BodyItem } from "../types";

const Column = { render: () => null };

function names(surface: BodySurface) {
  return surface.visible().map((item) => item.name);
}

const none = () => undefined;
const wide = 10_000;

afterEach(() => vi.restoreAllMocks());

describe("the body surface", () => {
  it("starts as the form and the panel, in row order", () => {
    const surface = new BodySurface();
    expect(names(surface)).toEqual(["form", "panel"]);
    expect(surface.visible()[1]).toMatchObject({ width: 380, minWidth: 320, maxWidth: 640, collapsible: true });
  });

  it("places a column before the form, between, and after the panel", () => {
    const surface = new BodySurface();
    surface.add({ name: "nav", component: Column, width: 200 }, { before: "form" });
    surface.add({ name: "summary", component: Column }, { after: "form" });
    surface.add({ name: "assistant", component: Column }, { after: "panel" });
    expect(names(surface)).toEqual(["nav", "form", "summary", "panel", "assistant"]);
  });

  it("moves the panel left of the form, and hides the form with a warning", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const surface = new BodySurface();
    surface.move("panel", { before: "form" });
    expect(names(surface)).toEqual(["panel", "form"]);
    surface.hide("form");
    expect(names(surface)).toEqual(["panel"]);
    expect(surface.has("form")).toBe(true);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain("page.body.hide('form')");
  });

  it("clears every column, built-ins included", () => {
    const surface = new BodySurface();
    surface.add({ name: "summary", component: Column });
    surface.clear();
    expect(names(surface)).toEqual([]);
    surface.show("form");
    expect(names(surface)).toEqual(["form"]);
  });

  it("refuses an add under a built-in's name", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const surface = new BodySurface();
    surface.add({ name: "panel", component: Column });
    expect(surface.visible()[1].component).toBeUndefined();
    expect(warn.mock.calls[0][0]).toContain("page.body.add('panel')");
  });

  it("drops a key the body does not read, and warns once", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const surface = new BodySurface();
    surface.add({ name: "summary", component: Column, label: "Summary" });
    expect(surface.visible()[2]).toEqual({ name: "summary", component: Column });
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain("body.add('summary'): key 'label'");
  });
});

describe("columnBounds", () => {
  it("flexes without a width, and bounds a fixed column by the script defaults", () => {
    expect(columnBounds({ name: "a" })).toBeNull();
    expect(columnBounds({ name: "a", width: 280 })).toEqual({ width: 280, minWidth: 240, maxWidth: 640 });
    expect(columnBounds({ name: "a", width: 100, minWidth: 200 })).toEqual({ width: 200, minWidth: 200, maxWidth: 640 });
    expect(SCRIPT_COLUMN_DEFAULTS).toEqual({ minWidth: 240, maxWidth: 640 });
  });
});

describe("projectBody", () => {
  const form: BodyItem = { name: "form" };
  const panel: BodyItem = { name: "panel", width: 380, minWidth: 320, maxWidth: 640, collapsible: true };

  it("gives a flex column no width and a fixed column its default", () => {
    const [a, b] = projectBody([form, panel], none, wide);
    expect(a).toMatchObject({ width: 0, bounds: null, edge: null, dropped: false });
    expect(b).toMatchObject({ width: 380, collapsible: true, collapsed: false, edge: "left" });
  });

  it("puts the edge on the side facing the nearest flex column, and none without one", () => {
    const columns = projectBody([{ name: "nav", width: 200 }, form, panel, { name: "aside" }], none, wide);
    expect(columns.map((column) => column.edge)).toEqual(["right", null, "left", null]);
    expect(projectBody([panel, { name: "nav", width: 200 }], none, wide).map((c) => c.edge)).toEqual([null, null]);
  });

  it("lets the reader's memory win over the script's width, clamped to the bounds", () => {
    const memory: Record<string, Remembered> = { panel: { width: 9000, collapsed: true } };
    const [, b] = projectBody([form, panel], (name) => memory[name], wide);
    expect(b.width).toBe(640);
    expect(b.collapsed).toBe(true);
    const [, c] = projectBody([form, panel], () => ({ width: Number.NaN }), wide);
    expect(c.width).toBe(380);
  });

  it("ignores a remembered collapse on a column that is not collapsible", () => {
    const [, b] = projectBody([form, { name: "s", width: 300 }], () => ({ collapsed: true }), wide);
    expect(b.collapsed).toBe(false);
  });

  it("gives a collapsible flex column a chevron edge, and a strip once shut", () => {
    const items: BodyItem[] = [form, panel, { name: "assistant", collapsible: true }];
    const [, p, a] = projectBody(items, none, wide);
    expect(a).toMatchObject({ bounds: null, collapsible: true, edge: "left" });
    expect(p.edge).toBe("left");
    const shut = projectBody(items, (name) => (name === "assistant" ? { collapsed: true } : undefined), wide);
    expect(shut[2]).toMatchObject({ collapsed: true, width: 0 });
    expect(shut[1].edge).toBe("left");
    expect(projectBody([{ name: "only", collapsible: true }], none, wide)[0].edge).toBe("right");
  });

  it("no longer counts a shut flex column as the one to keep at 320px", () => {
    const shut = () => ({ collapsed: true });
    const [f, p] = projectBody([{ name: "form", collapsible: true }, panel], shut, 500);
    expect(f).toMatchObject({ collapsed: true, dropped: false });
    expect(p).toMatchObject({ dropped: false, edge: null });
  });

  it("drops fixed columns from the outside in until the flex column keeps 320px", () => {
    const items: BodyItem[] = [
      { name: "nav", width: 240 },
      form,
      { name: "between", width: 240 },
      panel,
      { name: "right", width: 240 },
    ];
    const dropped = (available: number) =>
      projectBody(items, none, available)
        .filter((column) => column.dropped)
        .map((column) => column.item.name);
    const all = 240 + FLEX_MIN_WIDTH + 240 + 380 + 240 + 4;
    expect(dropped(all)).toEqual([]);
    expect(dropped(all - 1)).toEqual(["right"]);
    expect(dropped(240 + FLEX_MIN_WIDTH + 240 + 380 + 3)).toEqual(["right"]);
    expect(dropped(240 + FLEX_MIN_WIDTH + 240 + 380 + 2)).toEqual(["nav", "right"]);
    expect(dropped(FLEX_MIN_WIDTH + 240 + 380 + 2)).toEqual(["nav", "right"]);
    expect(dropped(FLEX_MIN_WIDTH + 240 + 380 + 1)).toEqual(["nav", "panel", "right"]);
    expect(dropped(FLEX_MIN_WIDTH + 240 + STRIP_WIDTH + 2)).toEqual(["nav", "panel", "right"]);
    expect(dropped(FLEX_MIN_WIDTH + 240 + STRIP_WIDTH + 1)).toEqual(["nav", "between", "panel", "right"]);
  });

  it("draws a dropped collapsible column as a strip, with no edge", () => {
    const [, b] = projectBody([form, panel], none, 390);
    expect(b).toMatchObject({ dropped: true, collapsed: true, edge: null });
    const [, c] = projectBody([form, { name: "s", width: 300 }], none, 390);
    expect(c).toMatchObject({ dropped: true, collapsed: false });
  });

  it("drops fixed columns that overflow on their own, and nothing on an unmeasured row", () => {
    const [p, s] = projectBody([panel, { name: "s", width: 300 }], none, 400);
    expect(p.dropped).toBe(false);
    expect(s.dropped).toBe(true);
    expect(projectBody([panel, { name: "s", width: 300 }], none, 300)[0]).toMatchObject({ dropped: true, collapsed: true });
    expect(projectBody([form, panel], none, 0)[1].dropped).toBe(false);
  });
});

describe("dragOutcome", () => {
  const bounds = { width: 380, minWidth: 320, maxWidth: 640 };

  it("resizes within the range and snaps near the default", () => {
    expect(dragOutcome(true, 400, 50, bounds, true)).toEqual({ width: 450 });
    expect(dragOutcome(true, 400, -15, bounds, true)).toEqual({ width: 380 });
    expect(dragOutcome(true, 400, 900, bounds, true)).toEqual({ width: 640 });
  });

  it("collapses 60px under the minimum without committing the squashed width", () => {
    expect(dragOutcome(true, 400, 259 - 400, bounds, true)).toEqual({ width: 400, toggle: true });
    expect(dragOutcome(true, 400, 260 - 400, bounds, true)).toEqual({ width: 320 });
    expect(dragOutcome(true, 400, 100 - 400, bounds, false)).toEqual({ width: 320 });
  });

  it("reopens a strip only after a deliberate pull", () => {
    expect(dragOutcome(false, 400, 10, bounds, true)).toEqual({});
    expect(dragOutcome(false, 400, 40, bounds, true)).toEqual({ toggle: true });
  });
});
