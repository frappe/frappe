import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App, Ref } from "vue";
import type { SetupFlowResult, SetupStepSlotProps } from "../types";

const capture = vi.hoisted(() => vi.fn());
const telemetry = vi.hoisted(() => ({ on: null as unknown as Ref<boolean> }));
vi.mock("../../../telemetry", async () => {
  const { reactive, ref } = await import("vue");
  telemetry.on = ref(true);
  return { useTelemetry: () => reactive({ capture, isEnabled: telemetry.on }) };
});

// jsdom has no matchMedia; the header's theme switch reads the OS scheme through it.
const media = (matches = false) => () => ({
  matches,
  addEventListener: () => {},
  removeEventListener: () => {},
});
vi.stubGlobal("matchMedia", media());

let app: App | null = null;

async function mountFlow(
  steps: { name: string; required?: boolean }[] = [
    { name: "goal" },
    { name: "invite" },
  ],
  props: {
    backButton?: boolean;
    themeToggle?: boolean;
    step?: string;
    "onUpdate:step"?: (name: string) => void;
  } = {},
) {
  const { default: SetupFlow } = await import("../SetupFlow.vue");
  const finished: SetupFlowResult[] = [];
  let slot!: SetupStepSlotProps;
  const el = document.createElement("div");
  app = createApp({
    render: () =>
      h(
        SetupFlow,
        {
          steps,
          ...props,
          onFinish: (result: SetupFlowResult) => finished.push(result),
        },
        {
          step: (props: SetupStepSlotProps) => {
            slot = props;
            return h("p", props.step.name);
          },
        },
      ),
  });
  app.mount(el);
  return { el, finished, slot: () => slot };
}

afterEach(() => {
  app?.unmount();
  app = null;
  capture.mockReset();
  if (telemetry.on) telemetry.on.value = true;
});

describe("SetupFlow", () => {
  it("stops at a required step when setup is skipped, and will not skip past it", async () => {
    const { el, finished, slot } = await mountFlow([
      { name: "goal" },
      { name: "password", required: true },
      { name: "invite" },
    ]);

    // The header's Skip setup opens a dialog whose last button confirms it.
    (el.querySelector("button") as HTMLButtonElement | null)?.click();
    await nextTick();
    await new Promise((resolve) => setTimeout(resolve, 50));
    const confirm = [...document.querySelectorAll("button")]
      .filter((b) => b.textContent?.trim() === "Skip setup")
      .at(-1);
    confirm?.click();
    await nextTick();
    expect(finished).toEqual([]);
    expect(el.textContent).toContain("password");

    slot().skip();
    await nextTick();
    expect(el.textContent).toContain("password");

    slot().done();
    await nextTick();
    expect(finished).toEqual([
      { skipped: true, completed: ["password"], skippedSteps: [] },
    ]);
    expect(capture).toHaveBeenCalledWith("setup_skipped", { step: "goal" });
  });

  it("forgets Skip setup when the user goes back to continue", async () => {
    const { el, finished, slot } = await mountFlow([
      { name: "goal" },
      { name: "password", required: true },
      { name: "invite" },
    ]);
    (el.querySelector("button") as HTMLButtonElement | null)?.click();
    await nextTick();
    await new Promise((resolve) => setTimeout(resolve, 50));
    [...document.querySelectorAll("button")]
      .filter((b) => b.textContent?.trim() === "Skip setup")
      .at(-1)
      ?.click();
    await nextTick();
    expect(el.textContent).toContain("password");

    [...el.querySelectorAll("button")]
      .find((b) => b.textContent?.includes("Back"))
      ?.click();
    await nextTick();
    expect(el.textContent).toContain("goal");

    slot().done();
    await nextTick();
    slot().done();
    await nextTick();
    expect(el.textContent).toContain("invite");
    expect(finished).toEqual([]);
  });

  it("walks the steps and reports what was done and skipped", async () => {
    const { el, finished, slot } = await mountFlow();
    expect(el.textContent).toContain("goal");

    slot().done({ choice: "course" });
    await nextTick();
    expect(el.textContent).toContain("invite");

    slot().skip();
    await nextTick();
    expect(finished).toEqual([
      { skipped: false, completed: ["goal"], skippedSteps: ["invite"] },
    ]);
    expect(capture).toHaveBeenCalledWith(
      "setup_step_completed",
      expect.objectContaining({ step: "goal", choice: "course" }),
    );
    expect(capture).toHaveBeenLastCalledWith(
      "setup_finished",
      expect.objectContaining({ skipped: false, steps_completed: 1 }),
    );
  });

  it("moves once on a double click, and finishes once", async () => {
    const { el, finished, slot } = await mountFlow();

    const first = slot();
    first.done();
    first.done();
    await nextTick();
    expect(el.textContent).toContain("invite");
    expect(finished).toEqual([]);

    // The second click of a double click lands after the step has changed.
    first.done();
    await nextTick();
    expect(el.textContent).toContain("invite");
    expect(finished).toEqual([]);

    slot().done();
    slot().skip();
    await nextTick();
    expect(finished).toHaveLength(1);
  });

  it("lets the host place Back itself", async () => {
    const { el, slot } = await mountFlow(
      [{ name: "goal" }, { name: "invite" }],
      { backButton: false },
    );
    expect(slot().canGoBack).toBe(false);
    slot().back();
    await nextTick();
    expect(el.textContent).toContain("goal");

    slot().done();
    await nextTick();
    expect(el.textContent).not.toContain("Back");
    expect(slot().canGoBack).toBe(true);

    slot().back();
    await nextTick();
    expect(el.textContent).toContain("goal");
  });

  it("offers no way out of a required step", async () => {
    const { el, slot } = await mountFlow([
      { name: "password", required: true },
      { name: "goal" },
    ]);
    expect(el.textContent).not.toContain("Skip setup");

    slot().done();
    await nextTick();
    expect(el.textContent).toContain("Skip setup");
    // Done is done: a required step is not offered again through Back.
    expect(el.textContent).not.toContain("Back");
  });

  it("lets a step with screens of its own take Back first", async () => {
    const { el, slot } = await mountFlow([{ name: "goal" }, { name: "import" }]);
    slot().done();
    await nextTick();

    const screen = ref<"upload" | "review">("review");
    slot().handleBack({
      canGoBack: () => screen.value === "review",
      back: () => (screen.value = "upload"),
    });
    await nextTick();
    slot().back();
    await nextTick();
    expect(screen.value).toBe("upload");
    expect(el.textContent).toContain("import");
    expect(capture).toHaveBeenCalledWith("setup_back", {
      from_step: "import",
      within_step: true,
    });

    slot().back();
    await nextTick();
    expect(el.textContent).toContain("goal");
  });

  it("shows Back on the first step when the step can go back itself", async () => {
    const { el, slot } = await mountFlow([{ name: "import" }, { name: "invite" }]);
    expect(el.textContent).not.toContain("Back");
    slot().handleBack({ canGoBack: () => true, back: () => {} });
    await nextTick();
    expect(slot().canGoBack).toBe(true);
    expect(el.textContent).toContain("Back");
  });

  it("forgets a step's Back once the step changes", async () => {
    const { slot } = await mountFlow([{ name: "import" }, { name: "invite" }]);
    const back = vi.fn();
    const first = slot();
    first.handleBack({ canGoBack: () => true, back });
    first.done();
    await nextTick();
    first.handleBack({ canGoBack: () => true, back });
    slot().back();
    await nextTick();
    expect(back).not.toHaveBeenCalled();
    expect(slot().step.name).toBe("import");
  });

  it("puts the host's own actions in the header", async () => {
    const { default: SetupFlow } = await import("../SetupFlow.vue");
    const el = document.createElement("div");
    app = createApp({
      render: () =>
        h(
          SetupFlow,
          { steps: [{ name: "goal" }] },
          {
            step: () => h("p", "goal"),
            actions: () => h("button", { "aria-label": "Switch to dark mode" }),
          },
        ),
    });
    app.mount(el);
    const header = el.querySelector("header")!;
    expect(header.querySelector('[aria-label="Switch to dark mode"]')).not.toBeNull();
    expect(header.textContent).toContain("Skip setup");
  });

  it("switches between light and dark from the header", async () => {
    const { el } = await mountFlow();
    const toggle = () =>
      el.querySelector('header button[aria-label^="Switch to"]') as HTMLButtonElement;
    const before = document.documentElement.getAttribute("data-theme");
    toggle().click();
    await nextTick();
    const after = document.documentElement.getAttribute("data-theme");
    expect(after).not.toBe(before);
    expect(toggle().getAttribute("aria-label")).toBe(
      after === "dark" ? "Switch to light mode" : "Switch to dark mode",
    );
    toggle().click();
  });

  it("leaves the theme switch out for an app without a dark mode", async () => {
    const { el } = await mountFlow(undefined, { themeToggle: false });
    expect(el.querySelector('header button[aria-label^="Switch to"]')).toBeNull();
    expect(el.querySelector("header")!.textContent).toContain("Skip setup");
  });

  it("opens the step it is given and reports each step it moves to", async () => {
    const seen: string[] = [];
    const { el, slot } = await mountFlow(
      [{ name: "goal" }, { name: "email" }, { name: "invite" }],
      { step: "email", "onUpdate:step": (name) => seen.push(name) },
    );
    expect(el.textContent).toContain("email");
    expect(el.textContent).toContain("Step 2 of 3");
    slot().done();
    await nextTick();
    expect(seen).toEqual(["invite"]);
  });

  it("moves to a step the host names later", async () => {
    const step = ref("goal");
    const { el } = await mountFlow(
      [{ name: "goal" }, { name: "email" }, { name: "invite" }],
      {
        get step() {
          return step.value;
        },
        "onUpdate:step": (name) => (step.value = name),
      },
    );
    step.value = "invite";
    await nextTick();
    expect(el.textContent).toContain("Step 3 of 3");
    step.value = "email";
    await nextTick();
    expect(el.textContent).toContain("Step 2 of 3");
  });

  it("sends its first events at once when telemetry is already on", async () => {
    await mountFlow();
    expect(capture).toHaveBeenCalledWith("setup_started");
    expect(capture).toHaveBeenCalledWith("setup_step_viewed", { step: "goal" });
  });

  it("holds its first events until telemetry is on", async () => {
    await import("../../../telemetry");
    telemetry.on.value = false;
    await mountFlow();
    expect(capture).not.toHaveBeenCalledWith("setup_started");
    telemetry.on.value = true;
    await nextTick();
    expect(capture).toHaveBeenCalledWith("setup_started");
    expect(capture).toHaveBeenCalledWith("setup_step_viewed", { step: "goal" });
  });
});
