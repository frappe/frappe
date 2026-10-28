import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import type { App } from "vue";

vi.mock("../../../composables/useLinkSearch", async () => {
  const { ref } = await import("vue");
  return {
    useLinkSearch: () => ({
      data: ref([{ label: "Administrator", value: "Administrator" }]),
      loading: ref(false),
      search: () => {},
    }),
  };
});

import Link from "../Link.vue";

const apps: App[] = [];

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

async function mountLink(props: Record<string, unknown>) {
  const onRedirect = vi.fn();
  const host = document.createElement("div");
  document.body.appendChild(host);
  const app = createApp({
    render: () =>
      h(Link, { doctype: "User", modelValue: "Administrator", onRedirect, ...props }),
  });
  app.mount(host);
  apps.push(app);
  await nextTick();
  return { arrow: host.querySelector<HTMLElement>("[data-slot=redirect]"), onRedirect };
}

describe("Link redirect arrow", () => {
  it("draws the arrow for redirectable and emits redirect on click", async () => {
    const { arrow, onRedirect } = await mountLink({ redirectable: true });
    expect(arrow?.tagName).toBe("BUTTON");
    expect(arrow?.querySelector(".lucide-arrow-up-right")).not.toBeNull();
    arrow!.click();
    expect(onRedirect).toHaveBeenCalledWith("Administrator");
  });

  it("draws an anchor to the record when href is given", async () => {
    const { arrow } = await mountLink({ href: "/apps/desk/user/Administrator", redirectable: true });
    expect(arrow?.tagName).toBe("A");
    expect(arrow?.getAttribute("href")).toBe("/apps/desk/user/Administrator");
  });

  it("draws no arrow without href or redirectable, or without a value", async () => {
    expect((await mountLink({})).arrow).toBeNull();
    expect((await mountLink({ redirectable: true, modelValue: null })).arrow).toBeNull();
  });
});
