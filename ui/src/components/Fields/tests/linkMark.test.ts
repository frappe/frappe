// The mark before a Link value: a dot from the target's colour, else an avatar from its image.
// A read-only LinkField takes the value from `LinkMarksKey`, keyed by the Link's doctype and name.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import LinkField from "../LinkField.vue";
import LinkMark from "../LinkMark.vue";
import { LinkMarksKey } from "../types";
import type { FieldMeta, LinkMarkSource } from "../types";

const getDocumentFields = vi.hoisted(() => vi.fn());
vi.mock("../../../api", () => ({ getDocumentFields }));

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = host = undefined;
});

async function mount(component: object, props: Record<string, unknown>, marks?: Record<string, string>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => h(component, props) });
  if (marks) app.provide(LinkMarksKey, ref(marks));
  app.mount(host);
  await nextTick();
  return host;
}

const color: LinkMarkSource = { kind: "color", field: "color" };
const image: LinkMarkSource = { kind: "image", field: "image" };

describe("LinkMark", () => {
  it("draws a named colour as an ink token dot", async () => {
    const el = await mount(LinkMark, { source: color, value: "blue" });
    expect(el.querySelector("[data-slot=link-mark]")?.className).toContain("text-ink-blue-6");
  });

  it("draws a hex colour as is", async () => {
    const el = await mount(LinkMark, { source: color, value: "#ff0000" });
    expect((el.querySelector("[data-slot=link-mark]") as HTMLElement).style.backgroundColor).toBe("#ff0000");
  });

  it("draws nothing for an empty or unknown colour", async () => {
    expect((await mount(LinkMark, { source: color, value: "" })).querySelector("[data-slot=link-mark]")).toBeNull();
    app?.unmount();
    expect((await mount(LinkMark, { source: color, value: "chartreuse" })).querySelector("[data-slot=link-mark]")).toBeNull();
  });

  it("shows initials of the title for an empty image", async () => {
    const el = await mount(LinkMark, { source: image, value: null, text: "Frappe Technologies" });
    expect(el.textContent).toContain("F");
  });

  it("draws nothing for an image source when the Link value is empty", async () => {
    expect((await mount(LinkMark, { source: image, value: null, text: "" })).querySelector("[data-slot=link-mark]")).toBeNull();
  });

  it("draws nothing without a source", async () => {
    expect((await mount(LinkMark, { value: "blue" })).querySelector("[data-slot=link-mark]")).toBeNull();
  });
});

describe("LinkField", () => {
  beforeEach(() => getDocumentFields.mockReset().mockResolvedValue({ data: null }));

  const field: FieldMeta = {
    fieldname: "status",
    fieldtype: "Link",
    options: "CRM Lead Status",
    label: "Status",
    readOnly: true,
    linkMark: color,
  };

  it("shows the host's mark for its value before the text", async () => {
    const el = await mount(
      LinkField,
      { field, modelValue: "New" },
      { "CRM Lead Status::New": "green", "CRM Lead Status::Lost": "red" }
    );
    const dot = el.querySelector("[data-slot=link-value] [data-slot=link-mark]");
    expect(dot?.className).toContain("text-ink-green-7");
  });

  it("shows no dot for a value no mark is found for", async () => {
    const el = await mount(LinkField, { field, modelValue: "Other" }, { "CRM Lead Status::New": "green" });
    expect(el.querySelector("[data-slot=link-mark]")).toBeNull();
  });

  it("reads the mark of a picked value the host holds none for, once", async () => {
    getDocumentFields.mockResolvedValue({ data: { color: "red" } });
    const value = ref("New");
    host = document.createElement("div");
    document.body.appendChild(host);
    app = createApp({ render: () => h(LinkField, { field, modelValue: value.value }) });
    app.provide(LinkMarksKey, ref({ "CRM Lead Status::New": "green" }));
    app.mount(host);
    await nextTick();
    expect(getDocumentFields).not.toHaveBeenCalled();
    value.value = "Picked";
    await nextTick();
    await nextTick();
    expect(getDocumentFields).toHaveBeenCalledWith("CRM Lead Status", "Picked", ["color"]);
    expect(host.querySelector("[data-slot=link-mark]")?.className).toContain("text-ink-red-");
    value.value = "New";
    await nextTick();
    expect(getDocumentFields).toHaveBeenCalledTimes(1);
  });

  it("reads the mark of a value at once when no host provides marks", async () => {
    getDocumentFields.mockResolvedValue({ data: { color: "blue" } });
    const el = await mount(LinkField, { field, modelValue: "Quick" });
    await nextTick();
    await nextTick();
    expect(getDocumentFields).toHaveBeenCalledWith("CRM Lead Status", "Quick", ["color"]);
    expect(el.querySelector("[data-slot=link-mark]")?.className).toContain("text-ink-blue-");
  });

  it("reads the mark of an unsaved default the host holds none for", async () => {
    getDocumentFields.mockResolvedValue({ data: { color: "red" } });
    await mount(LinkField, { field, modelValue: "Default" }, {});
    expect(getDocumentFields).toHaveBeenCalledWith("CRM Lead Status", "Default", ["color"]);
  });
});
