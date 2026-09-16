// The form surface: the layout's sections as built-ins, a field name refused with
// the owning verb named, the strip reached as `tabs`, and the neighbour kept on a part.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
  createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
}));

import { FormSurface, resetFormWarnings } from "../form";
import { FormTabsSurface } from "../formTabs";
import type { RawMetaField } from "@framework/ui/components/FormLayout/types";

const Part = { render: () => null };

const FIELDS = [
  { fieldname: "overview", fieldtype: "Section Break" },
  { fieldname: "deal_value", fieldtype: "Currency" },
  { fieldname: "pricing", fieldtype: "Section Break" },
  { fieldname: "products_tab", fieldtype: "Tab Break" },
] as RawMetaField[];

function makeSurface() {
  const tabs = new FormTabsSurface({ tabs: () => [], doc: () => ({}) });
  const form = new FormSurface({ fields: () => FIELDS }, tabs);
  form.provideBuiltins(() => [{ name: "overview", label: "Overview" }, { name: "pricing" }]);
  return form;
}

function names(form: FormSurface) {
  return form.visible().map((item) => item.name);
}

beforeEach(() => {
  resetFormWarnings();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("the form surface", () => {
  it("starts as the layout's sections, in layout order", () => {
    expect(names(makeSurface())).toEqual(["overview", "pricing"]);
  });

  it("carries the strip as `tabs`", () => {
    const form = makeSurface();
    expect(form.tabs).toBeInstanceOf(FormTabsSurface);
  });

  it("hides, relabels and moves a section", () => {
    const form = makeSurface();
    form.update("pricing", { label: "Commercials" });
    form.move("pricing", { before: "overview" });
    form.hide("overview");

    expect(form.visible()).toEqual([{ name: "pricing", label: "Commercials" }]);
  });

  it("clears the form; a later add draws", () => {
    const form = makeSurface();
    form.clear();
    form.add({ name: "note", component: Part });

    expect(names(form)).toEqual(["note"]);
  });

  it("refuses a field name and names page.fields", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const form = makeSurface();

    form.hide("deal_value");
    form.update("deal_value", { label: "Value" });
    form.move("deal_value", { before: "overview" });

    expect(names(form)).toEqual(["overview", "pricing"]);
    expect(warn.mock.calls.map((call) => call[0])).toEqual([
      '[record-page] page.form.hide("deal_value") — a field, not a section; page.fields.hide("…") is the verb.',
      '[record-page] page.form.update("deal_value") — a field, not a section; page.fields.update("…") is the verb.',
      '[record-page] page.form.move("deal_value") — a field, not a section; the Form Layout orders fields.',
    ]);
  });

  it("refuses a part named like a field, and one with no component", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const form = makeSurface();

    form.add([{ name: "deal_value", component: Part }, { name: "bare" }, { name: "kept", component: Part }]);

    expect(names(form)).toEqual(["overview", "pricing", "kept"]);
    expect(warn.mock.calls.map((call) => call[0])).toEqual([
      '[record-page] page.form.add("deal_value") — a field, not a section; a part needs a name of its own.',
      '[record-page] page.form.add("bare") — a part needs a component; dropped.',
    ]);
  });

  it("takes a layout break's fieldname as the section's own", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const form = makeSurface();
    form.hide("overview");

    expect(names(form)).toEqual(["pricing"]);
    expect(warn).not.toHaveBeenCalled();
  });

  it("keeps the neighbour on a part, so the host can choose the grain", () => {
    const form = makeSurface();
    form.add({ name: "score", component: Part }, { after: "deal_value" });
    form.add({ name: "chart", component: Part }, { after: "pricing" });
    form.move("chart", { before: "overview" });

    const positions = Object.fromEntries(
      form.resolve().map((entry) => [entry.item.name, entry.position]),
    );
    expect(positions).toEqual({
      overview: undefined,
      pricing: undefined,
      score: { after: "deal_value" },
      chart: { before: "overview" },
    });
  });

  it("drops a key the engine does not read, naming it", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const form = makeSurface();
    form.add({ name: "chart", component: Part, width: 320 } as any);

    expect(form.visible().at(-1)).toEqual({ name: "chart", component: Part });
    expect(warn.mock.calls[0][0]).toContain("key 'width'");
  });
});
