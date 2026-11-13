import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";
import type { SetupFlowResult, SetupStepSlotProps } from "../types";

const capture = vi.hoisted(() => vi.fn());
vi.mock("../../../telemetry", () => ({ useTelemetry: () => ({ capture }) }));

let app: App | null = null;

async function mountFlow(
  steps: { name: string; required?: boolean }[] = [
    { name: "goal" },
    { name: "invite" },
  ],
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
});
