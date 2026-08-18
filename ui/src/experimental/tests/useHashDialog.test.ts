// Driven by a real router on a memory history: the push/replace inference is
// the whole point of the composable, and a stubbed route object is not reactive
// enough to catch a write that pushed when it should have replaced.
import { describe, expect, it, vi } from "vitest";
import { createApp } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import type { Router } from "vue-router";
import { useHashDialog } from "../useHashDialog";

describe("useHashDialog", () => {
  it("is closed while the hash is not its own", async () => {
    const { dialog } = await mount(
      "page-scripts",
      "/deals?view=open#settings/profile",
    );

    expect(dialog.open.value).toBe(false);
    expect(dialog.segments.value).toEqual([]);
  });

  it("reads the segments after its root, decoded", async () => {
    const { dialog } = await mount(
      "page-scripts",
      "/deals#page-scripts/CRM%20Deal/greet",
    );

    expect(dialog.open.value).toBe(true);
    expect(dialog.segments.value).toEqual(["CRM Deal", "greet"]);
  });

  it("survives a segment that is not valid encoding", async () => {
    const { dialog } = await mount(
      "page-scripts",
      "/deals#page-scripts/100%25%zz",
    );

    expect(dialog.open.value).toBe(true);
    expect(dialog.segments.value).toHaveLength(1);
  });

  it("round-trips a segment the URL has to escape", async () => {
    const { dialog, router } = await mount("page-scripts");

    await dialog.write("CRM Deal", "greet");

    // Escaped once in the URL, and once only — the router owns that escaping.
    expect(router.currentRoute.value.fullPath).toContain("CRM%20Deal");
    expect(dialog.segments.value).toEqual(["CRM Deal", "greet"]);
  });

  it("pushes when it opens, so Back undoes the opening", async () => {
    const { dialog, pushed, replaced } = await mount("settings");

    await dialog.write("profile");

    expect(pushed()).toBe(1);
    expect(replaced()).toBe(0);
  });

  it("replaces a within-dialog change, so a tab switch adds no history", async () => {
    const { dialog, pushed, replaced } = await mount("settings");
    await dialog.write("profile");

    await dialog.write("users");

    expect(pushed()).toBe(1);
    expect(replaced()).toBe(1);
  });

  it("replaces on close, so Back does not re-open it", async () => {
    const { dialog, router } = await mount("settings", "/deals");
    await dialog.write("profile");

    await dialog.close();
    expect(dialog.open.value).toBe(false);

    await back(router);
    expect(router.currentRoute.value.fullPath).toBe("/deals");
  });

  it("leaves another dialog's hash alone when closed", async () => {
    const { dialog, router, replaced } = await mount(
      "settings",
      "/deals#page-scripts/CRM%20Deal",
    );

    await dialog.close();

    expect(replaced()).toBe(0);
    expect(router.currentRoute.value.hash).toBe("#page-scripts/CRM Deal");
  });

  it("preserves the query across a write and a close", async () => {
    const { dialog, router } = await mount(
      "settings",
      "/deals?view=open-deals",
    );

    await dialog.write("profile");
    expect(router.currentRoute.value.query).toEqual({ view: "open-deals" });

    await dialog.close();
    expect(router.currentRoute.value.fullPath).toBe("/deals?view=open-deals");
  });
});

async function mount(root: string, start = "/deals") {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:rest(.*)*", component: { render: () => null } }],
  });
  const app = createApp({ render: () => null });
  app.use(router);
  await router.replace(start);
  await router.isReady();

  const push = vi.spyOn(router, "push");
  const replace = vi.spyOn(router, "replace");
  const dialog = app.runWithContext(() => useHashDialog(root));

  return {
    router,
    pushed: () => push.mock.calls.length,
    replaced: () => replace.mock.calls.length,
    // The hash as handed to the router, before it decodes it back.
    written: () => (push.mock.calls.at(-1)?.[0] as { hash: string }).hash,
    // Every navigation is awaited, so an assertion reads settled state.
    dialog: {
      ...dialog,
      write: async (...segments: string[]) => {
        dialog.write(...segments);
        await settle(router);
      },
      close: async () => {
        dialog.close();
        await settle(router);
      },
    },
  };
}

function back(router: Router) {
  router.back();
  return settle(router);
}

// Navigation is async even on a memory history, and every assertion here reads
// settled state.
function settle(_router: Router) {
  return new Promise((resolve) => setTimeout(resolve, 0));
}
