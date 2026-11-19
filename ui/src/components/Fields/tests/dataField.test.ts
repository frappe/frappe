// A Data field's options set its keyboard, its open arrow and its IBAN grouping; none blocks a commit.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import TextField from "../TextField.vue";
import ReadOnlyField from "../ReadOnlyField.vue";
import { displayValue } from "../../FormLayout/displayValue";
import type { FieldMeta } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = host = undefined;
});

function data(options?: string, fieldtype = "Data"): FieldMeta {
  return { fieldname: "f", fieldtype, label: "F", options };
}

function render(field: FieldMeta, start: unknown = "") {
  const value = ref(start);
  const committed: unknown[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(TextField, {
        field,
        modelValue: value.value,
        "onUpdate:modelValue": (v: unknown) => (value.value = v),
        onChange: (v: unknown) => committed.push(v),
      }),
  });
  app.mount(host);
  const input = host.querySelector("input") as HTMLInputElement;
  return { value, committed, input, el: host };
}

function renderReadOnly(field: FieldMeta, value: unknown): HTMLElement {
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => h(ReadOnlyField, { field, modelValue: value }) });
  app.mount(host);
  return host;
}

async function type(input: HTMLInputElement, text: string) {
  input.dispatchEvent(new FocusEvent("focus"));
  input.value = text;
  input.dispatchEvent(new Event("input"));
  await nextTick();
}

async function commit(input: HTMLInputElement) {
  input.dispatchEvent(new Event("change"));
  input.dispatchEvent(new FocusEvent("blur"));
  await nextTick();
}

describe("a Data field's input", () => {
  it.each([
    [undefined, "text", null],
    ["Email", "text", "email"],
    ["URL", "text", "url"],
    ["Phone", "tel", null],
    ["Name", "text", null],
    ["IBAN", "text", null],
    ["Barcode", "text", null],
  ])("options %s sets type %s and inputmode %s", (options, inputType, inputmode) => {
    const { input } = render(data(options));
    expect(input.type).toBe(inputType);
    expect(input.getAttribute("inputmode")).toBe(inputmode);
  });

  it("commits an IBAN typed with spaces without them", async () => {
    const { input, value, committed } = render(data("IBAN"));
    await type(input, "DE89 3704 0044 0532 0130 00");
    expect(value.value).toBe("DE89370400440532013000");
    await commit(input);
    expect(committed).toEqual(["DE89370400440532013000"]);
  });

  it("shows an IBAN grouped once it loses focus", async () => {
    const { input } = render(data("IBAN"));
    await type(input, "DE89370400440532013000");
    expect(input.value).toBe("DE89370400440532013000");
    await commit(input);
    expect(input.value).toBe("DE89 3704 0044 0532 0130 00");
  });

  it("shows a stored IBAN grouped", () => {
    const { input } = render(data("IBAN"), "DE89370400440532013000");
    expect(input.value).toBe("DE89 3704 0044 0532 0130 00");
  });

  it("keeps what the person types while an IBAN has focus", async () => {
    const { input } = render(data("IBAN"));
    await type(input, "DE8937");
    expect(input.value).toBe("DE8937");
  });

  it.each([
    ["https://x.com", true],
    ["http://x.com/a?b=1", true],
    ["javascript:alert(1)", false],
    ["ftp://x", false],
    ["x.com", false],
  ])("shows the URL arrow for %s: %s", (url, shown) => {
    const { el } = render(data("URL"), url);
    const arrow = el.querySelector<HTMLAnchorElement>("[data-slot='open-url']");
    expect(!!arrow).toBe(shown);
    if (arrow) {
      expect(arrow.href).toBe(new URL(url).href);
      expect(arrow.target).toBe("_blank");
      expect(arrow.rel).toBe("noopener noreferrer");
    }
  });

  it("shows no URL arrow on a field with another option", () => {
    const { el } = render(data("Name"), "https://x.com");
    expect(el.querySelector("[data-slot='open-url']")).toBeNull();
  });

  it("commits an Email list as typed", async () => {
    const { input, committed } = render(data("Email"));
    await type(input, "a@x.com, b@y.com");
    await commit(input);
    expect(committed).toEqual(["a@x.com, b@y.com"]);
  });

  it.each(["Email", "URL", "Phone", "Name", "IBAN", "Barcode"])(
    "%s commits a value the server would refuse",
    async (options) => {
      const { input, committed } = render(data(options));
      await type(input, "not valid ✗");
      await commit(input);
      expect(committed).toHaveLength(1);
    }
  );
});

describe("a Data field nobody can edit", () => {
  it.each(["Data", "Read Only"])("draws a %s Email as a mailto link", (fieldtype) => {
    const el = renderReadOnly(data("Email", fieldtype), "a@x.com, b+c@y.com");
    const link = el.querySelector<HTMLAnchorElement>("[data-slot='mail-link']");
    expect(link?.getAttribute("href")).toBe("mailto:a@x.com,b%2Bc@y.com");
    expect(link?.textContent).toBe("a@x.com, b+c@y.com");
  });

  it("draws an https URL with the open arrow", () => {
    const el = renderReadOnly(data("URL"), "https://x.com");
    expect(el.textContent).toContain("https://x.com");
    expect(el.querySelector("[data-slot='open-url']")?.getAttribute("href")).toBe(
      "https://x.com/"
    );
  });

  it.each([
    ["URL", "javascript:alert(1)"],
    ["Phone", "+91 99999 99999"],
    ["Name", "Ada"],
    ["Barcode", "123456"],
  ])("draws a %s value %s as plain text", (options, value) => {
    const el = renderReadOnly(data(options), value);
    expect(el.querySelector("a")).toBeNull();
    expect(el.querySelector("[data-slot='read-value']")?.textContent?.trim()).toBe(value);
  });

  it("draws an empty Email as no link", () => {
    const el = renderReadOnly(data("Email"), "");
    expect(el.querySelector("a")).toBeNull();
  });

  it.each(["Data", "Read Only"])("shows a %s IBAN in groups of four", (fieldtype) => {
    expect(displayValue("DE89370400440532013000", data("IBAN", fieldtype))).toBe(
      "DE89 3704 0044 0532 0130 00"
    );
  });

  it("leaves an IBAN v1 does not group as stored", () => {
    expect(displayValue("BI4210000100010000332045181", data("IBAN"))).toBe(
      "BI4210000100010000332045181"
    );
  });
});
