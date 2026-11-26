import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";
import type { ListOption } from "../types";

let app: App | null = null;

const OPTIONS: ListOption[] = [
  {
    label: "Publish a course",
    value: "course",
    description: "Lessons, quizzes, a certificate.",
  },
  { label: "Onboard a team", value: "team", icon: "lucide-users" },
];

afterEach(() => {
  app?.unmount();
  app = null;
});

describe("ListStep", () => {
  it("lists each option with its description and hands back the one chosen", async () => {
    const { default: ListStep } = await import("../ListStep.vue");
    const chosen = vi.fn();
    const el = document.createElement("div");
    app = createApp({
      render: () => h(ListStep, { options: OPTIONS, onChoose: chosen }),
    });
    app.mount(el);

    expect(el.textContent).toContain("Lessons, quizzes, a certificate.");
    expect(el.querySelector(".lucide-users")).not.toBeNull();
    el.querySelectorAll("button")[1].click();
    await nextTick();
    expect(chosen).toHaveBeenCalledWith(OPTIONS[1]);
  });
});
