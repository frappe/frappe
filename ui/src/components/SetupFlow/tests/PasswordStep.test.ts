import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";

const call = vi.hoisted(() => vi.fn());
vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  call,
}));

let app: App | null = null;

async function mountStep() {
  const { default: PasswordStep } = await import("../PasswordStep.vue");
  const done = vi.fn();
  const el = document.createElement("div");
  document.body.appendChild(el);
  app = createApp({ render: () => h(PasswordStep, { onDone: done }) });
  app.mount(el);
  return { el, done };
}

async function type(el: HTMLElement, value: string) {
  const input = el.querySelector("input")!;
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await nextTick();
}

afterEach(() => {
  app?.unmount();
  app = null;
  call.mockReset();
});

describe("PasswordStep", () => {
  it("saves the first password and moves on", async () => {
    call.mockResolvedValue(null);
    const { el, done } = await mountStep();
    const submit = el.querySelector(
      'button[type="submit"]',
    ) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    await type(el, "Eastern_43A1W");
    expect(submit.disabled).toBe(false);
    el.querySelector("form")!.dispatchEvent(new Event("submit"));
    await nextTick();
    await nextTick();

    expect(call).toHaveBeenCalledWith(
      "frappe.core.doctype.user.user.set_first_password",
      { new_password: "Eastern_43A1W" },
    );
    expect(done).toHaveBeenCalledTimes(1);
  });

  it("shows the server's reason and stays when it refuses", async () => {
    call.mockRejectedValue({ messages: ["Better add a few more letters."] });
    const { el, done } = await mountStep();
    await type(el, "Eastern_43A1W");
    el.querySelector("form")!.dispatchEvent(new Event("submit"));
    await nextTick();
    await nextTick();
    await nextTick();

    expect(el.textContent).toContain("Better add a few more letters.");
    expect(done).not.toHaveBeenCalled();
  });
});
