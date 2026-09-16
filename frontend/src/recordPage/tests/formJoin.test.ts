// The join: the Details layout as `page.form` arranges it, with a part drawn at
// its neighbour's grain and landing in its neighbour's tab.
import { describe, expect, it } from "vitest";
import { Surface } from "../surface";
import { formItems, joinForm } from "../formJoin";
import { FORM_ITEM_KEYS } from "../types";
import type { FormItem } from "../types";
import type { FormLayoutSchema, Section } from "@framework/ui/components/FormLayout/types";

const Part = { render: () => null };
const page = { doc: {} };

const field = (fieldname: string) => ({ fieldname, fieldtype: "Data", label: fieldname }) as any;

const LAYOUT: FormLayoutSchema = [
  {
    name: "details",
    sections: [
      { name: "overview", label: "Overview", columns: [{ fields: [field("title"), field("status")] }] },
      { name: "pricing", label: "Pricing", columns: [{ fields: [field("deal_value")] }] },
    ],
  },
  { name: "products_tab", label: "Products", sections: [{ name: "items", columns: [{ fields: [field("products")] }] }] },
];

function makeSurface() {
  const form = new Surface<FormItem>({ surface: "form", keys: FORM_ITEM_KEYS });
  form.provideBuiltins(() => formItems(LAYOUT));
  return form;
}

function join(form: Surface<FormItem>) {
  return joinForm(LAYOUT, form.resolve(), page);
}

const sectionNames = (sections: Section[]) => sections.map((section) => section.name);

describe("the built-ins", () => {
  it("are the sections across every tab, in layout order", () => {
    expect(formItems(LAYOUT)).toEqual([
      { name: "overview", label: "Overview" },
      { name: "pricing", label: "Pricing" },
      { name: "items" },
    ]);
  });
});

describe("a part after a field", () => {
  it("is a cell of that field's column, carrying its neighbour", () => {
    const form = makeSurface();
    form.add({ name: "score", label: "Score", component: Part, props: { limit: 3 } }, { after: "deal_value" });

    const [details] = join(form);
    expect(details.sections[1].columns[0].parts).toEqual([
      { name: "score", label: "Score", component: Part, props: { limit: 3, page }, after: "deal_value" },
    ]);
    expect(sectionNames(details.sections)).toEqual(["overview", "pricing"]);
  });
});

describe("a part beside a part", () => {
  it("takes the neighbour's grain: a cell beside a cell", () => {
    const form = makeSurface();
    form.add({ name: "score", component: Part }, { after: "deal_value" });
    form.add({ name: "trend", component: Part }, { after: "score" });

    const [details] = join(form);
    expect(details.sections[1].columns[0].parts?.map((part) => [part.name, part.after])).toEqual([
      ["score", "deal_value"],
      ["trend", "score"],
    ]);
  });
});

describe("a built-in beside a field", () => {
  it("stays a section, in the field's tab", () => {
    const form = makeSurface();
    form.move("items", { after: "title" });

    const [details, products] = join(form);
    expect(sectionNames(details.sections)).toEqual(["overview", "pricing", "items"]);
    expect(details.sections[2].columns[0].fields.map((f) => f.fieldname)).toEqual(["products"]);
    expect(products.sections).toEqual([]);
  });
});

describe("a part beside a block", () => {
  it("is a block too, and a hidden neighbour still lends its tab", () => {
    const form = makeSurface();
    form.add({ name: "chart", component: Part }, { after: "items" });
    form.add({ name: "note", component: Part }, { after: "chart" });
    form.hide("items");

    const [, products] = join(form);
    expect(sectionNames(products.sections)).toEqual(["chart", "note"]);
  });
});

describe("a part after a section", () => {
  it("is a full-width section of its own, between the two", () => {
    const form = makeSurface();
    form.add({ name: "chart", label: "Pipeline", component: Part }, { after: "overview" });

    const [details] = join(form);
    expect(sectionNames(details.sections)).toEqual(["overview", "chart", "pricing"]);
    expect(details.sections[1]).toEqual({
      name: "chart",
      label: "Pipeline",
      collapsible: false,
      columns: [],
      part: { name: "chart", component: Part, props: { page } },
    });
  });

  it("lands in the neighbour's tab", () => {
    const form = makeSurface();
    form.add({ name: "note", component: Part }, { before: "items" });

    const [, products] = join(form);
    expect(sectionNames(products.sections)).toEqual(["note", "items"]);
  });

  it("with no position, goes to the end of the last tab", () => {
    const form = makeSurface();
    form.add({ name: "note", component: Part });

    const [details, products] = join(form);
    expect(sectionNames(details.sections)).toEqual(["overview", "pricing"]);
    expect(sectionNames(products.sections)).toEqual(["items", "note"]);
  });

  it("from two sources at one place, keeps both", () => {
    const form = makeSurface();
    form.add({ name: "first", component: Part }, { after: "overview" });
    form.add({ name: "second", component: Part }, { after: "overview" });

    const [details] = join(form);
    expect(sectionNames(details.sections)).toEqual(["overview", "second", "first", "pricing"]);
  });
});

describe("a section as an item", () => {
  it("hides, relabels, and moves across tabs", () => {
    const form = makeSurface();
    form.hide("overview");
    form.update("pricing", { label: "Commercials" });
    form.move("items", { before: "pricing" });

    const [details, products] = join(form);
    expect(sectionNames(details.sections)).toEqual(["items", "pricing"]);
    expect(details.sections[1].label).toBe("Commercials");
    expect(products.sections).toEqual([]);
  });

  it("keeps its fields; the source layout is never written", () => {
    const form = makeSurface();
    form.add({ name: "score", component: Part }, { after: "title" });
    form.add({ name: "chart", component: Part }, { after: "overview" });

    const [details] = join(form);
    expect(details.sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual(["title", "status"]);
    expect(LAYOUT[0].sections.length).toBe(2);
    expect(LAYOUT[0].sections[0].columns[0]).not.toHaveProperty("parts");
  });

  it("cleared, draws nothing", () => {
    const form = makeSurface();
    form.clear();

    expect(join(form).map((tab) => tab.sections)).toEqual([[], []]);
  });
});
