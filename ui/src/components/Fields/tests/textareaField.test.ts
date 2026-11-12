// A panel Small Text, Text or Long Text draws no label, description or error text, and grows from 28 to 128 with its lines.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import TextareaField from "../TextareaField.vue";
import { LINE_HEIGHT, MAX_HEIGHT, MAX_LINES, PADDING } from "../useTextareaGrow";
import type { FieldMeta } from "../types";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = host = undefined;
});

const field: FieldMeta = {
  fieldname: "f",
  fieldtype: "Small Text",
  label: "Label F",
  description: "A description",
  placeholder: "Add Label F...",
};

// jsdom has no layout: a textarea's content height is 8 + 20 per line of its value.
function stubScrollHeight() {
  Object.defineProperty(HTMLTextAreaElement.prototype, "scrollHeight", {
    configurable: true,
    get() {
      return PADDING + LINE_HEIGHT * (this.value.split("\n").length || 1);
    },
  });
}

function render(props: Record<string, unknown>, start = "") {
  const value = ref(start);
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(TextareaField, {
        field,
        modelValue: value.value,
        "onUpdate:modelValue": (v: string) => (value.value = v),
        ...props,
      }),
  });
  app.mount(host);
  return { value, textarea: host.querySelector("textarea") as HTMLTextAreaElement, el: host };
}

async function typeLines(textarea: HTMLTextAreaElement, lines: number) {
  textarea.value = Array.from({ length: lines }, (_, i) => `line ${i}`).join("\n");
  textarea.dispatchEvent(new Event("input"));
  await nextTick();
  await nextTick();
}

describe("a panel textarea", () => {
  it("draws no label, description or error text, and keeps the placeholder", () => {
    const { el, textarea } = render({ panel: true, error: "Bad value" });

    expect(el.querySelector("label")).toBeNull();
    expect(el.textContent).not.toContain("Label F");
    expect(el.textContent).not.toContain("A description");
    expect(el.textContent).not.toContain("Bad value");
    expect(textarea.getAttribute("placeholder")).toBe("Add Label F...");
  });

  it("is one row, and marked invalid when it holds an error", () => {
    const { textarea } = render({ panel: true, error: "Bad value" });

    expect(textarea.getAttribute("rows")).toBe("1");
    expect(textarea.getAttribute("aria-invalid")).toBe("true");
  });

  it("is 28 high when empty", () => {
    stubScrollHeight();
    expect(render({ panel: true }).textarea.style.height).toBe("28px");
  });

  it("is as high at first draw as the text needs, so a filled row opens at its rest height", () => {
    stubScrollHeight();
    expect(render({ panel: true }, "a\nb\nc").textarea.style.height).toBe("68px");
  });

  it("grows 20 per line while typing, and stops at six lines", async () => {
    stubScrollHeight();
    const { textarea } = render({ panel: true });
    const heights: string[] = [];

    for (const lines of [1, 2, 3, 4, 5, 6, 7, 12]) {
      await typeLines(textarea, lines);
      heights.push(textarea.style.height);
    }

    expect(heights).toEqual(["28px", "48px", "68px", "88px", "108px", "128px", "128px", "128px"]);
    expect(MAX_HEIGHT).toBe(PADDING + LINE_HEIGHT * MAX_LINES);
  });

  it("shrinks back when the text is deleted", async () => {
    stubScrollHeight();
    const { textarea } = render({ panel: true }, "a\nb\nc");

    await typeLines(textarea, 1);

    expect(textarea.style.height).toBe("28px");
  });
});

describe("a panel textarea whose width changes", () => {
  const observers: { callback: ResizeObserverCallback; disconnect: () => void; disconnected: boolean }[] = [];

  beforeEach(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        disconnected = false;
        constructor(public callback: ResizeObserverCallback) {
          observers.push(this);
        }
        observe() {}
        disconnect() {
          this.disconnected = true;
        }
      }
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    observers.length = 0;
  });

  async function resize(width: number) {
    observers[0].callback([{ contentRect: { width } } as ResizeObserverEntry], observers[0] as any);
    await new Promise((done) => requestAnimationFrame(done));
  }

  it("measures again, so wrapped text takes the lines the new width gives it", async () => {
    // Narrow: each line wraps in two.
    let narrow = false;
    Object.defineProperty(HTMLTextAreaElement.prototype, "scrollHeight", {
      configurable: true,
      get() {
        return PADDING + LINE_HEIGHT * (narrow ? 2 : 1);
      },
    });
    const { textarea } = render({ panel: true }, "one line");
    await resize(300);
    expect(textarea.style.height).toBe("28px");

    narrow = true;
    await resize(120);

    expect(textarea.style.height).toBe("48px");
  });

  it("ignores a change of height alone, which its own sizing causes", async () => {
    stubScrollHeight();
    const { textarea } = render({ panel: true }, "one line");
    await resize(300);
    textarea.style.height = "99px";

    await resize(300);

    expect(textarea.style.height).toBe("99px");
  });

  it("stops observing when it unmounts", () => {
    stubScrollHeight();
    render({ panel: true });

    app?.unmount();

    expect(observers[0].disconnected).toBe(true);
  });
});

describe("a textarea outside a panel", () => {
  it("draws its label, description and error text, and does not size itself", async () => {
    stubScrollHeight();
    const { el, textarea } = render({ error: "Bad value" });

    await typeLines(textarea, 4);

    expect(el.textContent).toContain("Label F");
    expect(el.textContent).toContain("Bad value");
    expect(textarea.style.height).toBe("");
  });
});
