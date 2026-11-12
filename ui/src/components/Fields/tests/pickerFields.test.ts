// A picker in a panel row draws no label, description or error text, shows the row's placeholder, and opens its popover when a pointer opened the row.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, reactive, ref } from "vue";
import type { App, Component } from "vue";

const api = vi.hoisted(() => ({
  searchDocuments: vi.fn(async () => ({ data: [{ value: "Administrator", label: "Administrator" }] })),
  getDocumentFields: vi.fn(),
}));
vi.mock("../../../api", () => api);

import { Link } from "../../Link";
import AutocompleteField from "../AutocompleteField.vue";
import DateField from "../DateField.vue";
import DatetimeField from "../DatetimeField.vue";
import DynamicLinkField from "../DynamicLinkField.vue";
import LinkField from "../LinkField.vue";
import SelectField from "../SelectField.vue";
import TimeField from "../TimeField.vue";
import PickerListFit from "../PickerListFit.vue";
import { fieldBoxKey } from "../fieldBox";
import { DocKey } from "../types";
import type { FieldMeta } from "../types";

const apps: App[] = [];

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

async function mount(component: Component, props: Record<string, unknown>, slots = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const app = createApp({ render: () => h(component, props, slots) });
  app.provide(DocKey, ref({ doctype_field: "User" }));
  app.mount(host);
  apps.push(app);
  await nextTick();
  return host;
}

const field = (fieldtype: string, extra: Partial<FieldMeta> = {}): FieldMeta => ({
  fieldname: "f",
  fieldtype,
  label: "Label F",
  description: "A description",
  placeholder: "Add the thing...",
  ...extra,
});

const PICKERS: [string, Component, FieldMeta, unknown][] = [
  ["Link", LinkField, field("Link", { options: "User" }), "Administrator"],
  ["Dynamic Link", DynamicLinkField, field("Dynamic Link", { options: "doctype_field" }), "Administrator"],
  ["Select", SelectField, field("Select", { options: "\nOpen\nClosed" }), null],
  ["Autocomplete", AutocompleteField, field("Autocomplete", { options: "Alpha\nBeta" }), null],
  ["Date", DateField, field("Date"), null],
  ["Datetime", DatetimeField, field("Datetime"), null],
  ["Time", TimeField, field("Time"), null],
];

describe.each(PICKERS)("%s in panel mode", (_name, component, meta, modelValue) => {
  const props = { field: meta, modelValue, error: "Bad value", panel: true };

  it("draws no label, description or error text", async () => {
    const el = await mount(component, props);
    expect(el.querySelector("label")).toBeNull();
    for (const text of ["Label F", "A description", "Bad value"]) {
      expect(el.textContent).not.toContain(text);
    }
  });

  it("shows the row's placeholder", async () => {
    const el = await mount(component, { ...props, modelValue: null });
    const input = el.querySelector("input");
    const shown = input ? input.getAttribute("placeholder") : el.textContent;
    expect(shown).toContain("Add the thing...");
  });

  it("opens its popover when a pointer opened the row, and not otherwise", async () => {
    const closed = await mount(component, props);
    expect(closed.querySelector('[aria-expanded="true"]')).toBeNull();
    const open = await mount(component, { ...props, openPicker: true });
    await nextTick();
    expect(open.querySelector('[aria-expanded="true"]')).not.toBeNull();
  });

  it("still draws its label, description and error text outside a panel", async () => {
    const el = await mount(component, { ...props, panel: false });
    for (const text of ["Label F", "Bad value"]) expect(el.textContent).toContain(text);
  });
});

describe("Dynamic Link in panel mode", () => {
  it("stays shut on a pointer open while no doctype is chosen", async () => {
    const meta = field("Dynamic Link", { options: "no_such_field" });
    const el = await mount(DynamicLinkField, { field: meta, modelValue: null, panel: true, openPicker: true });
    await nextTick();
    expect(el.querySelector('[aria-expanded="true"]')).toBeNull();
  });
});

describe("Link in panel mode", () => {
  async function mountLink(modelValue: string | null) {
    const state = reactive({ modelValue });
    const host = document.createElement("div");
    document.body.appendChild(host);
    const app = createApp({
      render: () =>
        h(
          Link,
          { doctype: "User", panel: true, modelValue: state.modelValue },
          { prefix: () => h("i", { "data-mark": "" }) }
        )
    });
    app.mount(host);
    apps.push(app);
    await nextTick();
    return { host, state };
  }

  it("hides the mark while typing and brings it back on commit", async () => {
    const { host, state } = await mountLink("Administrator");
    expect(host.querySelector("[data-mark]")).not.toBeNull();
    const input = host.querySelector("input")!;
    input.value = "Gue";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await nextTick();
    expect(host.querySelector("[data-mark]")).toBeNull();
    state.modelValue = "Guest";
    await nextTick();
    expect(host.querySelector("[data-mark]")).not.toBeNull();
  });

  it("is a ghost box the full column wide", async () => {
    const { host } = await mountLink(null);
    const trigger = host.querySelector("[data-slot=trigger]")!;
    expect(trigger.className).toContain("w-full");
    expect(trigger.getAttribute("data-variant")).toBe("ghost");
  });
});

describe("PickerListFit", () => {
  // jsdom lays nothing out: the panel's rect and a label's overflow are given.
  function mountList(
    bound: { left: number; width: number },
    overflowing: boolean,
    row: { bottom: number; ownMaxHeight?: string } = { bottom: 0 }
  ) {
    const panel = document.createElement("div");
    panel.setAttribute("data-picker-bound", "");
    panel.getBoundingClientRect = () => ({ left: bound.left, width: bound.width }) as DOMRect;
    const box = document.createElement("div");
    box.getBoundingClientRect = () => ({ bottom: row.bottom }) as DOMRect;
    panel.appendChild(box);
    const list = document.createElement("div");
    list.setAttribute("data-slot", "content");
    list.innerHTML = '<div role="option"><div class="truncate">A long option</div></div><div id="foot"></div>';
    const scroller = document.createElement("div");
    scroller.setAttribute("role", "presentation");
    scroller.style.maxHeight = row.ownMaxHeight ?? "";
    list.prepend(scroller);
    const label = list.querySelector<HTMLElement>(".truncate")!;
    Object.defineProperty(label, "scrollWidth", { value: overflowing ? 300 : 50 });
    Object.defineProperty(label, "clientWidth", { value: 100 });
    document.body.append(panel, list);
    const app = createApp(PickerListFit);
    app.provide(fieldBoxKey, ref(box));
    app.mount(list.querySelector("#foot")!);
    apps.push(app);
    return list;
  }

  it("caps the list at the panel's width", () => {
    expect(mountList({ left: 100, width: 380 }, false).style.maxWidth).toBe("380px");
  });

  it("keeps the list's left edge on the panel's when the viewport edge would shift it", () => {
    const left = innerWidth - 200;
    expect(mountList({ left, width: 380 }, false).style.maxWidth).toBe("190px");
  });

  it("caps the list's scroller at the room under the row, so the list opens below it", () => {
    const list = mountList({ left: 0, width: 380 }, false, { bottom: innerHeight - 300 });
    expect(list.querySelector<HTMLElement>('[role="presentation"]')!.style.maxHeight).toBe("284px");
  });

  it("keeps the list's own cap when the room under the row is larger", () => {
    const list = mountList({ left: 0, width: 380 }, false, { bottom: 0, ownMaxHeight: "200px" });
    expect(list.querySelector<HTMLElement>('[role="presentation"]')!.style.maxHeight).toBe(
      `min(200px, ${innerHeight - 16}px)`
    );
  });

  it("scrolls a row near the window's bottom up, so the list has room", () => {
    const scrolled = vi.fn();
    const scroller = document.createElement("div");
    scroller.style.overflowY = "auto";
    Object.defineProperty(scroller, "scrollHeight", { value: 900 });
    Object.defineProperty(scroller, "clientHeight", { value: 400 });
    scroller.scrollBy = scrolled as never;
    document.body.append(scroller);
    const box = document.createElement("div");
    box.getBoundingClientRect = () => ({ bottom: innerHeight - 14 }) as DOMRect;
    scroller.append(box);
    const list = document.createElement("div");
    list.setAttribute("data-slot", "content");
    list.innerHTML = '<div id="foot"></div>';
    document.body.append(list);
    const app = createApp(PickerListFit);
    app.provide(fieldBoxKey, ref(box));
    app.mount(list.querySelector("#foot")!);
    apps.push(app);
    // 120px of list and the 16px gap, less the 14px already free.
    expect(scrolled).toHaveBeenCalledWith({ top: 122, behavior: "instant" });
  });

  it("titles an option the list truncates, and none it does not", () => {
    for (const [overflowing, title] of [[true, "A long option"], [false, ""]] as const) {
      const list = mountList({ left: 0, width: 380 }, overflowing);
      const option = list.querySelector<HTMLElement>('[role="option"]')!;
      option.querySelector(".truncate")!.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
      expect(option.title).toBe(title);
    }
  });
});
