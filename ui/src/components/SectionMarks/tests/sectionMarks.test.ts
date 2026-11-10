// The marks a scroll area shows: when they draw, the card, and the keyboard.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import SectionMarks from "../SectionMarks.vue";

const SECTIONS = [
  { key: "a", label: "Appearance", description: "Theme and density." },
  { key: "b", label: "Email" },
  { key: "c", label: "Password" },
];

// Mounted with Vue's own `createApp`: this package has no `@vue/test-utils`.
let app: App | null = null;
let host: HTMLElement;
let elements: Record<string, HTMLElement & { scrollIntoView: ReturnType<typeof vi.fn> }>;

beforeAll(() => {
  globalThis.ResizeObserver ??= class {
    observe() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
});

afterEach(() => {
  app?.unmount();
  app = null;
  host.remove();
});

async function mountMarks(scrolls: boolean) {
  host = document.body.appendChild(document.createElement("div"));
  const viewport = document.createElement("div");
  Object.defineProperty(viewport, "clientHeight", { value: 300 });
  Object.defineProperty(viewport, "scrollHeight", { value: scrolls ? 900 : 300 });
  elements = Object.fromEntries(
    SECTIONS.map(({ key }) => [key, Object.assign(document.createElement("section"), { scrollIntoView: vi.fn() })])
  ) as typeof elements;
  app = createApp({
    render: () => h(SectionMarks, { viewport, sections: SECTIONS, find: (key: string) => elements[key] }),
  });
  app.mount(host);
  await nextTick();
  return host.querySelector("button");
}

function press(strip: HTMLElement, key: string) {
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  strip.dispatchEvent(event);
  return event;
}

describe("SectionMarks", () => {
  it("draws nothing while the area does not scroll", async () => {
    expect(await mountMarks(false)).toBeNull();
  });

  it("draws one mark per section while the area scrolls", async () => {
    const strip = (await mountMarks(true))!;
    expect(strip.querySelectorAll(":scope > span")).toHaveLength(3);
  });

  it("moves the chosen mark with the arrow keys and opens it on a keyboard click", async () => {
    const strip = (await mountMarks(true))!;
    strip.dispatchEvent(new FocusEvent("focus"));
    press(strip, "ArrowDown");
    press(strip, "ArrowDown");
    await nextTick();
    expect(strip.getAttribute("aria-label")).toBe("Jump to section: Password");
    strip.dispatchEvent(new MouseEvent("click", { detail: 0 }));
    expect(elements.c.scrollIntoView).toHaveBeenCalledOnce();
    expect(elements.a.scrollIntoView).not.toHaveBeenCalled();
  });

  it("shows the chosen section's card", async () => {
    const strip = (await mountMarks(true))!;
    strip.dispatchEvent(new FocusEvent("focus"));
    await nextTick();
    expect(host.textContent).toContain("Appearance");
    expect(host.textContent).toContain("Theme and density.");
  });

  it("closes the card on Escape without letting the key reach the dialog", async () => {
    const strip = (await mountMarks(true))!;
    const dialog = vi.fn();
    host.addEventListener("keydown", dialog);
    strip.dispatchEvent(new FocusEvent("focus"));
    await nextTick();
    expect(press(strip, "Escape").defaultPrevented).toBe(true);
    await nextTick();
    expect(host.textContent).not.toContain("Theme and density.");
    expect(dialog).not.toHaveBeenCalled();
    press(strip, "Escape");
    expect(dialog).toHaveBeenCalledOnce();
  });
});
