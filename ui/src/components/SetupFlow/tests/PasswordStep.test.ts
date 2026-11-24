import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";

const call = vi.hoisted(() => vi.fn());
vi.mock("frappe-ui", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  call,
}));

let app: App | null = null;

async function mountStep(props: { confirm?: boolean } = { confirm: false }) {
  const { default: PasswordStep } = await import("../PasswordStep.vue");
  const done = vi.fn();
  const el = document.createElement("div");
  document.body.appendChild(el);
  app = createApp({
    render: () => h(PasswordStep, { ...props, onDone: done }),
  });
  app.mount(el);
  return { el, done };
}

async function type(el: HTMLElement, value: string, field = 0) {
  const input = el.querySelectorAll("input")[field] as HTMLInputElement;
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

  it("moves on when the server says a password already exists", async () => {
    call.mockRejectedValue({
      exc_type: "PermissionError",
      messages: ["You already have a password. Change it from your settings."],
    });
    const { el, done } = await mountStep();
    await type(el, "Eastern_43A1W");
    el.querySelector("form")!.dispatchEvent(new Event("submit"));
    await nextTick();
    await nextTick();
    await nextTick();

    expect(done).toHaveBeenCalledTimes(1);
    expect(el.textContent).not.toContain("already have a password");
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

    await type(el, "Eastern_43A1W!");
    expect(el.textContent).not.toContain("Better add a few more letters.");
  });

  it("tells a preview when it can save, so the preview's button follows its own", async () => {
    const { default: PasswordStep } = await import("../PasswordStep.vue");
    const ready: boolean[] = [];
    const el = document.createElement("div");
    document.body.appendChild(el);
    app = createApp({
      render: () => h(PasswordStep, { onReady: (r: boolean) => ready.push(r) }),
    });
    app.mount(el);

    await type(el, "Eastern_43A1W");
    await type(el, "Eastern_43A1W", 1);
    await type(el, "Eastern_43A1", 1);

    expect(ready).toEqual([false, true, false]);
  });

  it("asks twice by default, and saves only a matching pair", async () => {
    call.mockResolvedValue(null);
    const { el, done } = await mountStep({});
    const submit = el.querySelector(
      'button[type="submit"]',
    ) as HTMLButtonElement;
    expect(el.querySelectorAll("input")).toHaveLength(2);

    await type(el, "Eastern_43A1W");
    expect(submit.disabled).toBe(true);
    await type(el, "Eastern", 1);
    expect(el.textContent).not.toContain("do not match");
    await type(el, "Eastern_43A1X", 1);
    expect(submit.disabled).toBe(true);
    expect(el.textContent).toContain("The passwords do not match.");

    await type(el, "Eastern_43A1W", 1);
    expect(submit.disabled).toBe(false);
    expect(el.textContent).not.toContain("do not match");
    el.querySelector("form")!.dispatchEvent(new Event("submit"));
    await nextTick();
    await nextTick();
    expect(
      call.mock.calls.filter(([method]) =>
        method.endsWith("set_first_password"),
      ),
    ).toHaveLength(1);
    expect(done).toHaveBeenCalledTimes(1);
  });

  describe("strength meter", () => {
    const scored = (score: number, passed: boolean, warning = "") =>
      vi.fn(async (method: string) =>
        method.endsWith("test_password_strength")
          ? {
              score,
              feedback: {
                password_policy_validation_passed: passed,
                warning,
                suggestions: [],
              },
            }
          : null,
      );

    async function typeAndScore(el: HTMLElement, value: string) {
      vi.useFakeTimers();
      await type(el, value);
      await vi.advanceTimersByTimeAsync(300);
      vi.useRealTimers();
      await nextTick();
    }

    it("names how strong the password is once the site has scored it", async () => {
      call.mockImplementation(scored(3, true));
      const { el } = await mountStep();
      await typeAndScore(el, "Eastern_43A1W");
      expect(el.textContent).toContain("Strength: Good");
      const submit = el.querySelector(
        'button[type="submit"]',
      ) as HTMLButtonElement;
      expect(submit.disabled).toBe(false);
    });

    it("only informs on a weak password, so nothing below the field moves", async () => {
      call.mockImplementation(
        scored(1, false, "This is a very common password."),
      );
      const { el } = await mountStep();
      const before = el.querySelector("form")!.children.length;
      await typeAndScore(el, "password123");
      expect(el.textContent).toContain("Strength: Poor");
      expect(el.textContent).not.toContain("This is a very common password.");
      expect(el.querySelector("form")!.children.length).toBe(before);
      const submit = el.querySelector(
        'button[type="submit"]',
      ) as HTMLButtonElement;
      expect(submit.disabled).toBe(false);
    });

    it("shows no meter on a site without a password policy", async () => {
      call.mockResolvedValue({});
      const { el } = await mountStep();
      await typeAndScore(el, "Eastern_43A1W");
      expect(el.textContent).not.toContain("Strength");
      const submit = el.querySelector(
        'button[type="submit"]',
      ) as HTMLButtonElement;
      expect(submit.disabled).toBe(false);
    });
  });
});
