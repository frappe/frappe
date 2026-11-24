import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";

vi.mock("../../../telemetry", () => ({
  useTelemetry: () => ({ capture: vi.fn() }),
}));

// jsdom has no matchMedia; the header's theme switch reads the OS scheme through it.
const media = (matches = false) => () => ({
  matches,
  addEventListener: () => {},
  removeEventListener: () => {},
});
beforeEach(() => vi.stubGlobal("matchMedia", media()));

let app: App | null = null;

function mount(render: () => ReturnType<typeof h>) {
  const el = document.createElement("div");
  document.body.appendChild(el);
  app = createApp({ render });
  app.mount(el);
  return el;
}

afterEach(() => {
  app?.unmount();
  app = null;
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("PasswordStep", () => {
  it("reports how long the password is, never the password", async () => {
    const { default: PasswordStep } = await import("../PasswordStep.vue");
    const typed: unknown[] = [];
    const el = mount(() =>
      h(PasswordStep, { onInput: (length: unknown) => typed.push(length) }),
    );
    const input = el.querySelector("input")!;
    input.value = "Eastern_4";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await nextTick();

    expect(typed).toEqual([9]);
  });
});

describe("SetupPreviewLogin", () => {
  it("fills the email, shows one dot per typed character and enables Continue when the step can save", async () => {
    const { default: SetupPreviewLogin } =
      await import("../SetupPreviewLogin.vue");
    const length = ref(3);
    const ready = ref(false);
    const el = mount(() =>
      h(SetupPreviewLogin, {
        email: "owner@example.com",
        passwordLength: length.value,
        ready: ready.value,
      }),
    );
    const [email, password] = Array.from(el.querySelectorAll("input"));
    const submit = () =>
      Array.from(el.querySelectorAll("button")).find((b) =>
        b.textContent?.includes("Continue"),
      )!;

    expect(email.value).toBe("owner@example.com");
    expect(password.type).toBe("password");
    expect(password.value).toHaveLength(3);
    expect(submit().disabled).toBe(true);

    length.value = 8;
    await nextTick();
    expect(password.value).toHaveLength(8);
    expect(submit().disabled).toBe(true);

    ready.value = true;
    await nextTick();
    expect(submit().disabled).toBe(false);
  });
});

describe("SetupPreviewFrame", () => {
  async function mountFrame(reduced: boolean) {
    vi.stubGlobal("matchMedia", media(reduced));
    const { default: SetupPreviewFrame } =
      await import("../SetupPreviewFrame.vue");
    const expanded = ref(false);
    const handedOver = vi.fn();
    const el = mount(() =>
      h(
        SetupPreviewFrame,
        { expanded: expanded.value, onExpanded: handedOver },
        { default: () => h("p", "the app") },
      ),
    );
    return { el, expanded, handedOver };
  }

  it("keeps the preview out of reach of keyboard and screen readers", async () => {
    const { el } = await mountFrame(false);
    const frame = el.querySelector('[data-slot="setup-preview-window"]')!;

    expect(frame.hasAttribute("inert")).toBe(true);
    expect(frame.getAttribute("aria-hidden")).toBe("true");
    expect(frame.textContent).toBe("the app");
  });

  it("stacks two windows behind the preview and fades them as it grows", async () => {
    const { el, expanded } = await mountFrame(true);
    const layers = () =>
      Array.from(el.querySelectorAll('[data-slot="setup-preview-layer"]'));

    expect(layers()).toHaveLength(2);
    expect(layers().every((layer) => layer.getAttribute("aria-hidden") === "true")).toBe(true);
    expect(layers().some((layer) => layer.classList.contains("opacity-0"))).toBe(false);

    expanded.value = true;
    await nextTick();
    expect(layers().every((layer) => layer.classList.contains("opacity-0"))).toBe(true);
  });

  it("hands over at once under reduced motion", async () => {
    const { expanded, handedOver } = await mountFrame(true);
    expanded.value = true;
    await nextTick();

    expect(handedOver).toHaveBeenCalledTimes(1);
  });

  it("hands over even when the grow transition never reports its end", async () => {
    vi.useFakeTimers();
    const { expanded, handedOver } = await mountFrame(false);
    expanded.value = true;
    await nextTick();
    expect(handedOver).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(800);
    expect(handedOver).toHaveBeenCalledTimes(1);
  });

  it("puts a browser bar with the address and tabs above the app, and folds it on hand-over", async () => {
    vi.stubGlobal("matchMedia", media(false));
    const { default: SetupPreviewFrame } = await import("../SetupPreviewFrame.vue");
    const expanded = ref(false);
    const el = mount(() =>
      h(
        SetupPreviewFrame,
        {
          expanded: expanded.value,
          url: "acme.example.com/suite/notes",
          tabs: [{ title: "Acme Academy", active: true }],
        },
        { default: () => h("p", "the app"), "tab-icon": () => h("i", { class: "logo" }) },
      ),
    );
    const bar = el.querySelector('[data-slot="setup-preview-browser"]')!;
    expect(bar.textContent).toContain("acme.example.com/suite/notes");
    expect(bar.textContent).toContain("Acme Academy");
    expect(bar.querySelector(".logo")).not.toBeNull();
    expect(bar.className).toContain("grid-rows-[1fr]");

    expanded.value = true;
    await nextTick();
    expect(bar.className).toContain("grid-rows-[0fr]");
  });

  it("shows a cursor where the host points, and none when motion is reduced", async () => {
    const { default: SetupPreviewFrame } = await import("../SetupPreviewFrame.vue");
    const frame = (reduced: boolean) => {
      vi.stubGlobal("matchMedia", media(reduced));
      return mount(() =>
        h(SetupPreviewFrame, { cursor: { x: 40, y: 20 } }, { default: () => h("p", "app") }),
      );
    };

    const cursor = frame(false).querySelector<HTMLElement>('[data-slot="setup-preview-cursor"]');
    expect(cursor?.style.transform).toBe("translate(40px, 20px)");

    app?.unmount();
    expect(frame(true).querySelector('[data-slot="setup-preview-cursor"]')).toBeNull();
  });

  it("puts the signed-in person at the end of the address bar", async () => {
    const { default: SetupPreviewFrame } = await import("../SetupPreviewFrame.vue");
    const el = mount(() =>
      h(SetupPreviewFrame, { url: "acme.example.com/app", user: { name: "Owner Example" } }),
    );
    const bar = el.querySelector('[data-slot="setup-preview-browser"]')!;
    expect(bar.textContent).toContain("O");
    expect(bar.querySelector(".lucide-ellipsis-vertical")).not.toBeNull();
  });

  it("has no browser bar without an address", async () => {
    const { el } = await mountFrame(false);
    expect(el.querySelector('[data-slot="setup-preview-browser"]')).toBeNull();
  });
});

describe("SetupFlow preview", () => {
  it("puts the preview first and tells it which step and side are showing", async () => {
    const { default: SetupFlow } = await import("../SetupFlow.vue");
    const seen: number[] = [];
    const sides: string[] = [];
    const el = mount(() =>
      h(
        SetupFlow,
        { steps: [{ name: "goal" }], previewSide: "start" },
        {
          step: () => h("p", "step"),
          preview: ({ index, side }: { index: number; side: string }) => {
            seen.push(index);
            sides.push(side);
            return h("p", "preview");
          },
        },
      ),
    );

    expect(el.querySelector("aside")!.className).toContain("lg:order-first");
    expect(seen).toEqual([0]);
    expect(sides).toEqual(["start"]);
  });
});
