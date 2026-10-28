import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick } from "vue";
import ColorField from "../ColorField.vue";
import { focusField } from "../focusField";

afterEach(() => {
  document.body.innerHTML = "";
});

function cell(html: string) {
  const el = document.createElement("div");
  el.innerHTML = html;
  document.body.appendChild(el);
  return el;
}

const settle = () => new Promise((resolve) => setTimeout(resolve));

describe("focusField", () => {
  it("puts the cursor in a rich-text body before its toolbar", () => {
    const el = cell('<button>Bold</button><div contenteditable="true"></div>');
    focusField(el);
    expect(document.activeElement).toBe(el.querySelector("[contenteditable]"));
  });

  it("falls back to the first input", () => {
    const el = cell("<label>Qty</label><input />");
    focusField(el);
    expect(document.activeElement).toBe(el.querySelector("input"));
  });

  it("puts the cursor in a Color field's hex box, not its swatch", async () => {
    const el = cell("");
    const field = { fieldname: "color", fieldtype: "Color", label: "Color" };
    const app = createApp({ render: () => h(ColorField, { field, modelValue: "#171717" }) });
    app.mount(el);
    await nextTick();
    expect(el.querySelector("button[data-slot=swatch]")).not.toBeNull();
    focusField(el);
    expect(document.activeElement).toBe(el.querySelector("input"));
    app.unmount();
  });

  it("waits for a lazy control to draw its input", async () => {
    const el = cell("");
    focusField(el);
    el.innerHTML = '<button>Bold</button><div contenteditable="true"></div>';
    await settle();
    expect(document.activeElement).toBe(el.querySelector("[contenteditable]"));
  });

  it("waits from a button that asked for it", async () => {
    const el = cell("");
    const trigger = cell("<button>Open</button>").querySelector("button")!;
    trigger.focus();
    focusField(el);
    el.innerHTML = '<div contenteditable="true"></div>';
    await settle();
    expect(document.activeElement).toBe(el.querySelector("[contenteditable]"));
  });

  it("stops waiting once stopped", async () => {
    const el = cell("");
    const stop = focusField(el);
    stop();
    el.innerHTML = '<div contenteditable="true"></div>';
    await settle();
    expect(document.activeElement).toBe(document.body);
  });

  it("leaves the cursor where the reader moved it meanwhile", async () => {
    const el = cell("");
    const elsewhere = cell("<input />").querySelector("input")!;
    focusField(el);
    elsewhere.focus();
    el.innerHTML = '<div contenteditable="true"></div>';
    await settle();
    expect(document.activeElement).toBe(elsewhere);
  });
});
