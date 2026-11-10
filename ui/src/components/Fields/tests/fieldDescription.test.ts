import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App, Component } from "vue";
import CheckField from "../CheckField.vue";
import DateField from "../DateField.vue";
import LinkField from "../LinkField.vue";
import SelectField from "../SelectField.vue";
import TextField from "../TextField.vue";
import TextareaField from "../TextareaField.vue";
import { descriptionText } from "../fieldDescription";
import { sanitizeHtml } from "../../../utils/sanitize";

// happy-dom breaks DOMPurify (it keeps `onerror`), so this checks the wiring; a walk checks the purge.
vi.mock("../../../utils/sanitize", () => ({
  sanitizeHtml: vi.fn((html: string) => html.replace(/ onerror="[^"]*"/, "")),
}));

const HTML = 'One per line. Example: <br>CSV<br><code>JPG</code> <img src=x onerror="alert(1)">';

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

async function render(component: Component, fieldtype: string, error?: string) {
  host = document.createElement("div");
  document.body.appendChild(host);
  const field = { fieldname: "f", fieldtype, label: "F", options: "A\nB", description: HTML };
  app = createApp({ render: () => h(component, { field, modelValue: null, error }) });
  app.mount(host);
  await nextTick();
  return host.querySelector('[data-slot="description"]');
}

describe("field description", () => {
  it.each([
    ["Data", TextField],
    ["Check", CheckField],
    ["Select", SelectField],
    ["Small Text", TextareaField],
    ["Link", LinkField],
  ] as const)("draws a %s field's description as sanitized HTML", async (fieldtype, component) => {
    const description = await render(component, fieldtype);
    expect(description?.querySelectorAll("br")).toHaveLength(2);
    expect(description?.querySelector("code")?.textContent).toBe("JPG");
    expect(description?.querySelector("img")?.hasAttribute("onerror")).toBe(false);
    expect(description?.textContent).not.toContain("<br>");
  });

  it("hides the description while the field shows an error", async () => {
    const description = await render(TextField, "Data", "Not allowed");
    expect(description).toBeNull();
    expect(host?.textContent).toContain("Not allowed");
  });

  it("gives a date picker, which takes only a string, the text without tags", async () => {
    const description = await render(DateField, "Date");
    expect(description?.textContent).toBe("One per line. Example: CSV JPG");
  });

  it("sanitizes without styles or forms, as stored rich text is", async () => {
    await render(TextField, "Data");
    expect(sanitizeHtml).toHaveBeenCalledWith(HTML, {
      FORBID_TAGS: ["style", "form"],
      FORBID_ATTR: ["form", "formaction"],
      ADD_ATTR: ["target"],
    });
  });

  it("passes a description with no markup through as text", () => {
    expect(descriptionText("plain")).toBe("plain");
    expect(descriptionText("<ul><li>CSV</li><li>JPG</li></ul>")).toBe("CSV JPG");
    expect(descriptionText("")).toBeUndefined();
  });
});
