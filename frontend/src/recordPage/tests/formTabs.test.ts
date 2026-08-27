// The Form Layout tabs surface (wayfinder ticket 73) as executable claims: a
// tab addressed by identity, an overlay that beats `depends_on` in both
// directions, a reader that resolves both, and a replay that stages.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
  createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
}));

import { FormTabsSurface, resetFormTabWarnings } from "../formTabs";
import type { FormTabsSurfaceHost } from "../formTabs";
import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";

/** Three tabs: one named, one conditional, one with nothing but a label. */
const LAYOUT: FormLayoutSchema = [
  { name: "lead_details", label: "Lead Details", sections: [] },
  {
    name: "products",
    label: "Products",
    dependsOn: "eval:doc.with_products",
    sections: [],
  },
  { label: "Contacts & More", sections: [] },
];

function makeSurface(host: Partial<FormTabsSurfaceHost> = {}) {
  return new FormTabsSurface({
    tabs: () => LAYOUT,
    doc: () => ({ with_products: 0 }),
    ...host,
  });
}

beforeEach(() => {
  resetFormTabWarnings();
  vi.restoreAllMocks();
});

describe("addressing a tab", () => {
  it("takes the author's name, and the label slugified when there is none", () => {
    const formTabs = makeSurface();

    expect(formTabs.has("lead_details")).toBe(true);
    expect(formTabs.has("contacts-more")).toBe(true);
    expect(formTabs.has("Contacts & More")).toBe(false);
  });

  it("sees a tab the layout hides, because `has` asks who authored it", () => {
    // `products` is off under this doc; a surface that could not see it would
    // leave a script unable to `show()` the very tab it wants.
    const formTabs = makeSurface();

    expect(formTabs.has("products")).toBe(true);
    expect(formTabs.get("products")?.hidden).toBe(true);
  });

  it("says nothing while the layout is still loading", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const formTabs = makeSurface({ tabs: () => [] });

    formTabs.hide("lead_details");

    expect(warn).not.toHaveBeenCalled();
    // Recorded anyway: the op must survive the window it was written in.
    expect(formTabs.resolve()).toEqual({ lead_details: { hidden: true } });
  });

  it("names a tab the layout does not carry, once", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const formTabs = makeSurface();

    formTabs.hide("nope");
    formTabs.hide("nope");

    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain('page.formTabs.hide("nope")');
  });
});

describe("the overlay", () => {
  it("folds an identity's ops into one override, later winning", () => {
    const formTabs = makeSurface();

    formTabs.hide("lead_details");
    formTabs.update("lead_details", { label: "Lead" });
    formTabs.show("lead_details");

    expect(formTabs.resolve()).toEqual({
      lead_details: { hidden: false, label: "Lead" },
    });
  });

  it("takes `label` and drops every other key, naming it", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const formTabs = makeSurface();

    formTabs.update("products", { label: "Items", dependsOn: "eval:1" } as any);

    expect(formTabs.resolve().products).toEqual({ label: "Items" });
    expect(warn.mock.calls[0][0]).toContain("{ dependsOn }");
  });

  it("points `update({ hidden })` at the verbs that mean it", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const formTabs = makeSurface();

    formTabs.update("products", { hidden: true } as any);

    expect(formTabs.resolve().products).toEqual({});
    expect(warn.mock.calls[0][0]).toContain("use hide()/show()");
  });

  it("keeps `__proto__` off `Object.prototype`", () => {
    const formTabs = makeSurface();
    formTabs.hide("__proto__");

    expect(formTabs.resolve()["__proto__"]).toEqual({ hidden: true });
    expect(({} as any).hidden).toBeUndefined();
  });
});

describe("reading a tab back", () => {
  it("resolves `hidden` from the doc, with the override the last word", () => {
    const doc = { with_products: 0 };
    const formTabs = makeSurface({ doc: () => doc });

    expect(formTabs.get("products")?.hidden).toBe(true);
    formTabs.show("products");
    expect(formTabs.get("products")?.hidden).toBe(false);

    // And in the other direction, over a `depends_on` that now says yes.
    doc.with_products = 1;
    formTabs.hide("products");
    expect(formTabs.get("products")?.hidden).toBe(true);
  });

  it("hands back the label a script wrote, beside the address it wrote it at", () => {
    const formTabs = makeSurface();
    formTabs.update("contacts-more", { label: "People" });

    expect(formTabs.get("contacts-more")).toEqual({
      name: undefined,
      identity: "contacts-more",
      label: "People",
      hidden: false,
    });
  });

  it("reports the label the strip actually draws", () => {
    // An unlabelled tab renders as "Details" once the strip is on screen, so a
    // `get` that answered `''` would disagree with the button beside it.
    const formTabs = makeSurface({
      tabs: () => [
        { name: "first", sections: [] },
        { name: "second", label: "Second", sections: [] },
      ],
    });

    expect(formTabs.get("first")?.label).toBe("Details");
  });

  it("drops that fallback when it is the only tab left", () => {
    // One tab draws no strip at all, so there is no blank button to fill in.
    const formTabs = makeSurface({
      tabs: () => [
        { name: "first", sections: [] },
        { name: "second", label: "Second", sections: [] },
      ],
    });
    formTabs.hide("second");

    expect(formTabs.get("first")?.label).toBe("");
  });

  it("refuses a write through the snapshot", () => {
    const formTabs = makeSurface();
    const tab = formTabs.get("lead_details")!;

    expect(() => {
      (tab as any).hidden = true;
    }).toThrow(/page\.formTabs/);
  });

  it("answers null for a tab that is not there", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(makeSurface().get("nope")).toBeNull();
  });
});

describe("the replay", () => {
  it("publishes a replay's ops in one flush, at the commit", () => {
    const formTabs = makeSurface();
    formTabs.hide("products");

    formTabs.beginReplay();
    formTabs.hide("lead_details");
    // Mid-replay the host still sees last replay's overlay, never a half-built
    // one — the strip would otherwise be torn down and rebuilt between them.
    expect(formTabs.resolve()).toEqual({ products: { hidden: true } });

    formTabs.commitReplay();
    expect(formTabs.resolve()).toEqual({ lead_details: { hidden: true } });
  });

  it("tells a source about its own work inside its own handler", () => {
    const formTabs = makeSurface();

    formTabs.beginReplay();
    formTabs.hide("lead_details");

    expect(formTabs.get("lead_details")?.hidden).toBe(true);
  });

  it("publishes only on the outermost commit", () => {
    // A script's own `page.refresh()` re-enters the replay.
    const formTabs = makeSurface();

    formTabs.beginReplay();
    formTabs.beginReplay();
    formTabs.hide("products");
    formTabs.commitReplay();
    expect(formTabs.resolve()).toEqual({});

    formTabs.commitReplay();
    expect(formTabs.resolve()).toEqual({ products: { hidden: true } });
  });
});
