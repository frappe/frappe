// A focused input hard-cuts its placeholder, so the text is cut to the box and ends in an ellipsis.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";
import { useFittedPlaceholder } from "../fittedPlaceholder";

const apps: App[] = [];

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
});

describe("useFittedPlaceholder", () => {
  const restores: (() => void)[] = [];
  afterEach(() => restores.splice(0).forEach((restore) => restore()));

  const widthOf = (text: string) => text.length * 10;

  function mountFitted(text: string, inputWidth: number, focused = true) {
    const original = { observer: globalThis.ResizeObserver, create: document.createElement.bind(document) };
    globalThis.ResizeObserver = class {
      constructor(private callback: () => void) {}
      observe() {
        this.callback();
      }
      disconnect() {}
    } as never;
    const spy = vi.spyOn(document, "createElement").mockImplementation(((tag: string) => {
      if (tag !== "canvas") return original.create(tag);
      return { getContext: () => ({ measureText: (shown: string) => ({ width: widthOf(shown) }) }) };
    }) as never);
    let result!: ReturnType<typeof useFittedPlaceholder>;
    const app = createApp({
      setup() {
        result = useFittedPlaceholder(() => text);
        return () => h("span");
      },
    });
    app.mount(document.createElement("div"));
    apps.push(app);
    const input = document.createElement("input");
    Object.defineProperty(input, "clientWidth", { value: inputWidth });
    if (focused) result.fit(input);
    restores.push(() => {
      spy.mockRestore();
      globalThis.ResizeObserver = original.observer;
    });
    return { result, restore: restores[restores.length - 1] };
  }

  it("keeps a placeholder that fits, and cuts one that does not at an ellipsis", async () => {
    const { result, restore } = mountFitted("Add Dynamic Link target field...", 200);
    await nextTick();
    // 10px a character, half a pixel of slack: 19 characters fit, the last one the "…".
    expect(result.placeholder.value).toBe("Add Dynamic Link t…");
    restore();
    const roomy = mountFitted("Add Name...", 200);
    await nextTick();
    expect(roomy.result.placeholder.value).toBe("Add Name...");
    roomy.restore();
  });

  it("shows the full text until an input has focus", () => {
    const { result, restore } = mountFitted("Add Dynamic Link target field...", 200, false);
    expect(result.placeholder.value).toBe("Add Dynamic Link target field...");
    restore();
  });
});
