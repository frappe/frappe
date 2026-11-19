// The frame surface: two regions that stay put, and the bands a script places around them.
import { afterEach, describe, expect, it, vi } from "vitest";
import { FrameSurface, projectFrame } from "../frame";
import { withRegisteringSource } from "../context";

const Band = { render: () => null };

function names(surface: FrameSurface) {
  return surface.visible().map((item) => item.name);
}

afterEach(() => vi.restoreAllMocks());

describe("the frame surface", () => {
  it("starts as the two regions, in column order", () => {
    expect(names(new FrameSurface())).toEqual(["header", "body"]);
  });

  it("places a band before, between and after the regions", () => {
    const surface = new FrameSurface();
    surface.add({ name: "strip", component: Band, gutter: false }, { before: "header" });
    surface.add({ name: "banner", component: Band }, { after: "header" });
    surface.add({ name: "footer", component: Band }, { after: "body" });
    expect(names(surface)).toEqual(["strip", "header", "banner", "body", "footer"]);
  });

  it("drops a key the frame does not read, and warns once", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const surface = new FrameSurface();
    surface.add({ name: "banner", component: Band, label: "Banner" });
    expect(surface.visible()[2]).toEqual({ name: "banner", component: Band });
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain("frame.add('banner'): key 'label'");
  });

  it("refuses to move a region, and warns", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const surface = new FrameSurface();
    surface.move("header", { after: "body" });
    expect(names(surface)).toEqual(["header", "body"]);
    expect(warn.mock.calls[0][0]).toContain("page.frame.move('header')");
  });

  it("orders bands only: a region named in order() is left out, with a warning", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const surface = new FrameSurface();
    surface.add({ name: "banner", component: Band }, { after: "header" });
    surface.add({ name: "footer", component: Band }, { after: "body" });
    surface.order(["body", "footer", "header", "banner"]);
    expect(names(surface)).toEqual(["footer", "banner", "header", "body"]);
    expect(warn).toHaveBeenCalledTimes(2);
    expect(warn.mock.calls[0][0]).toContain("page.frame.order('body')");
  });

  it("refuses a band under a region's name, and keeps the rest of the block", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const surface = new FrameSurface();
    surface.add([{ name: "body", component: Band }, { name: "footer", component: Band }]);
    expect(names(surface)).toEqual(["header", "body", "footer"]);
    expect(warn.mock.calls[0][0]).toContain("page.frame.add('body')");
  });

  it("hides a region and a band, and clear blanks the page", () => {
    const surface = new FrameSurface();
    surface.add({ name: "banner", component: Band }, { after: "header" });
    surface.hide("header");
    surface.hide("banner");
    expect(names(surface)).toEqual(["body"]);
    surface.clear();
    expect(names(surface)).toEqual([]);
    expect(surface.has("header")).toBe(true);
    surface.show("header");
    expect(names(surface)).toEqual(["header"]);
  });

  it("orders two scripts at one place by run order, then by the anchor", async () => {
    const surface = new FrameSurface();
    await withRegisteringSource("first", async () =>
      surface.add({ name: "a_banner", component: Band }, { after: "header" }),
    );
    await withRegisteringSource("second", async () => {
      surface.add({ name: "b_first", component: Band }, { after: "header" });
      surface.add({ name: "b_second", component: Band }, { after: "a_banner" });
    });
    expect(names(surface)).toEqual(["header", "b_first", "a_banner", "b_second", "body"]);
  });
});

describe("projectFrame", () => {
  it("buckets the visible bands by the regions' places", () => {
    const surface = new FrameSurface();
    surface.add({ name: "strip", component: Band }, { before: "header" });
    surface.add({ name: "banner", component: Band }, { after: "header" });
    surface.add({ name: "footer", component: Band }, { after: "body" });
    surface.add({ name: "gone", component: Band }, { after: "body" });
    surface.hide("gone");
    const projection = projectFrame(surface.resolve());
    expect(projection.before.map((band) => band.name)).toEqual(["strip"]);
    expect(projection.between.map((band) => band.name)).toEqual(["banner"]);
    expect(projection.after.map((band) => band.name)).toEqual(["footer"]);
    expect(projection.header).toBe(true);
    expect(projection.body).toBe(true);
  });

  it("reports a hidden region, and shows both with no list at all", () => {
    const surface = new FrameSurface();
    surface.hide("body");
    expect(projectFrame(surface.resolve())).toMatchObject({ header: true, body: false });
    expect(projectFrame([])).toMatchObject({ header: true, body: true, before: [], after: [] });
  });
});
