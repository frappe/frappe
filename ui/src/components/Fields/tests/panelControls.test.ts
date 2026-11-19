import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import AttachField from "../AttachField.vue";
import CheckField from "../CheckField.vue";
import RatingField from "../RatingField.vue";

/** In a panel row Check, Rating and Attach draw only the control: the row owns text and box. */

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(component: object, fieldtype: string, start: unknown, extra: object = {}) {
  const doc = ref(start);
  const committed: unknown[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(component, {
        field: {
          fieldname: "f",
          fieldtype,
          label: "Label",
          description: "A description",
          placeholder: "Add Label...",
          reqd: 1,
          ...extra,
        },
        panel: true,
        error: "Required",
        modelValue: doc.value,
        "onUpdate:modelValue": (value: unknown) => (doc.value = value),
        onChange: (value: unknown) => committed.push(value),
      }),
  });
  app.mount(host);
  return { doc, committed, root: host };
}

async function settle() {
  for (let i = 0; i < 3; i++) await nextTick();
}

describe("a panel Check", () => {
  it("draws no label, description or error text, and marks the error on the checkbox", () => {
    const { root } = render(CheckField, "Check", 0);
    expect(root.textContent?.trim()).toBe("");
    expect(root.querySelector("input")?.getAttribute("aria-invalid")).toBe("true");
  });

  it("toggles once from a click anywhere in the box, and not from the checkbox's own click", async () => {
    const { root, committed } = render(CheckField, "Check", 0);
    (root.firstElementChild as HTMLElement).click();
    await settle();
    root.querySelector("input")!.click();
    await settle();
    expect(committed).toEqual([1, 0]);
  });
});

describe("a panel Rating", () => {
  it("draws no label, description or error text", () => {
    const { root } = render(RatingField, "Rating", 0.5);
    expect(root.textContent?.trim()).toBe("");
  });

  it("mutes the stars when read-only", () => {
    const { root } = render(RatingField, "Rating", 0.5, { readOnly: 1 });
    expect(root.firstElementChild?.classList.contains("opacity-50")).toBe(true);
  });
});

describe("a panel Attach", () => {
  it("reads the field's placeholder when empty, with no ↗ or ×", () => {
    const { root } = render(AttachField, "Attach", null);
    expect(root.textContent?.trim()).toBe("Add Label...");
    expect(root.querySelector("a, [data-slot=clear]")).toBeNull();
  });

  it("shows the file name, opens the file from ↗ and clears from ×", async () => {
    const { root, committed, doc } = render(AttachField, "Attach", "/files/report.pdf");
    expect(root.querySelector("button[data-slot=control]")?.textContent?.trim()).toBe("report.pdf");
    expect(root.querySelector("a")?.getAttribute("href")).toBe("/files/report.pdf");
    (root.querySelector("[data-slot=clear]") as HTMLElement).click();
    await settle();
    expect(committed).toEqual([null]);
    expect(doc.value).toBeNull();
  });

  it("draws a 20px thumbnail before an Attach Image's name", () => {
    const { root } = render(AttachField, "Attach Image", "/files/cover.png");
    const thumb = root.querySelector("img");
    expect(thumb?.classList.contains("size-5")).toBe(true);
    expect(root.querySelector("button[data-slot=control]")?.textContent?.trim()).toBe("cover.png");
  });

  it("puts × before ↗ in DOM order, so ↗ keeps the right-edge slot", () => {
    const { root } = render(AttachField, "Attach", "/files/report.pdf");
    const clear = root.querySelector("[data-slot=clear]") as HTMLElement;
    const link = root.querySelector("a") as HTMLElement;
    expect(clear.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(link.parentElement).toBe(clear.parentElement);
    expect(clear.parentElement?.lastElementChild).toBe(link);
  });

  it("keeps ↗ but no × for a read-only row", () => {
    const { root } = render(AttachField, "Attach", "/files/report.pdf", { readOnly: 1 });
    expect(root.querySelector("a")).not.toBeNull();
    expect(root.querySelector("[data-slot=clear]")).toBeNull();
  });
});
