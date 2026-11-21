import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";

vi.mock("../../../telemetry", () => ({
  useTelemetry: () => ({ capture: vi.fn() }),
}));

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
  it("fills the email, shows one dot per typed character and enables Continue at the minimum", async () => {
    const { default: SetupPreviewLogin } =
      await import("../SetupPreviewLogin.vue");
    const length = ref(3);
    const el = mount(() =>
      h(SetupPreviewLogin, {
        email: "owner@example.com",
        passwordLength: length.value,
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
    expect(submit().disabled).toBe(false);
  });
});

describe("SetupPreviewFrame", () => {
  async function mountFrame(reduced: boolean) {
    vi.stubGlobal("matchMedia", () => ({ matches: reduced }));
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
});

describe("SetupFlow preview", () => {
  it("puts the preview first and tells it which step is showing", async () => {
    const { default: SetupFlow } = await import("../SetupFlow.vue");
    const seen: number[] = [];
    const el = mount(() =>
      h(
        SetupFlow,
        { steps: [{ name: "goal" }], previewSide: "start" },
        {
          step: () => h("p", "step"),
          preview: ({ index }: { index: number }) => {
            seen.push(index);
            return h("p", "preview");
          },
        },
      ),
    );

    expect(el.querySelector("aside")!.className).toContain("lg:order-first");
    expect(seen).toEqual([0]);
  });
});
