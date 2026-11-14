// The editor header: the crumbs while a child table is open, and its controls.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerShell } from "@/router/routeFor";
import EditorHeader from "../EditorHeader.vue";
import type { EditorMode } from "../pendingEdits";

const apps: App[] = [];

afterEach(() => {
  apps.splice(0).forEach((app) => app.unmount());
  document.body.innerHTML = "";
});

function mountHeader(
  mode: EditorMode,
  openParent: () => void,
  extra: Record<string, unknown> = {},
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/:any(.*)*", name: "list", component: { render: () => null } },
    ],
  });
  registerShell({
    boot: {
      app: "frappe",
      shell_base: "/apps/frappe",
      prefixes: { frappe: { app: "frappe", modular: false } },
    } as unknown as Boot,
    addresses: new Addresses({
      doctypes: {
        DocType: ["doctype", "core"],
        "Walk Order": ["walk-order", "core"],
      },
      modules: { core: "Core" },
    }),
    router,
  });
  const props = {
    doctype: "Walk Order",
    canvas: null,
    dirty: false,
    canUndo: false,
    canRedo: false,
    canSave: false,
    saving: false,
    mode,
    modes: [mode],
    developerMode: false,
    finder: {
      canvas: null,
      scope: null,
      panelShown: true,
      find: () => {},
      findSetting: () => {},
    },
    finderOpen: false,
    draft: false,
    tab: "editor",
    childCrumbs: [
      { label: "Items", onClick: () => {} },
      { label: "Walk Order Item" },
    ],
    onOpenParent: openParent,
    ...extra,
  };
  const root = document.body.appendChild(document.createElement("div"));
  const app = createApp(
    defineComponent({ render: () => h(EditorHeader, props) }),
  );
  app.use(router);
  app.mount(root);
  apps.push(app);
  return root;
}

function crumb(root: Element, label: string) {
  return [...root.querySelectorAll<HTMLElement>("[data-crumbs] > *")].find(
    (one) => one.textContent!.trim() === label,
  )!;
}

it.each([
  ["Design", "Walk Order"],
  ["Customize", "Customize"],
] as const)(
  "opens the parent's editor from the parent's crumb in %s",
  async (mode, label) => {
    const openParent = vi.fn();
    const root = mountHeader(mode, openParent);
    await nextTick();

    crumb(root, label).click();

    expect(openParent).toHaveBeenCalledTimes(1);
  },
);

describe("the header's controls", () => {
  it("has a search button with the shortcut hint, and an icon on each tab", async () => {
    const root = mountHeader("Design", vi.fn());
    await nextTick();
    expect(root.querySelector("[data-editor-finder]")!.textContent).toContain(
      "Search fields, settings, properties",
    );
    for (const icon of ["layout-list", "settings", "eye"])
      expect(root.querySelector(`.lucide-${icon}`)).not.toBeNull();
  });

  it("hides Undo and Redo on Preview, keeping their place", async () => {
    const group = (root: Element) =>
      root.querySelector('[aria-label="Undo"]')!.closest("[class*='lg:flex']")!;
    const editor = group(mountHeader("Design", vi.fn()));
    const preview = group(mountHeader("Design", vi.fn(), { tab: "preview" }));
    await nextTick();
    expect([
      editor.classList.contains("invisible"),
      preview.classList.contains("invisible"),
      preview.hasAttribute("inert"),
    ]).toEqual([false, true, true]);
  });

  it("says Not saved while dirty", async () => {
    const root = mountHeader("Design", vi.fn(), { dirty: true });
    await nextTick();
    expect(root.textContent).toContain("Not saved");
  });

  it("shows no layout crumb on a draft", async () => {
    const saved = mountHeader("Design", vi.fn(), { childCrumbs: [] });
    const draft = mountHeader("Design", vi.fn(), {
      childCrumbs: [],
      draft: true,
    });
    await nextTick();
    expect([
      saved.querySelector("[data-layout-crumb]") !== null,
      draft.querySelector("[data-layout-crumb]"),
    ]).toEqual([true, null]);
    expect(
      draft
        .querySelector("[data-crumbs]")!
        .textContent!.replace(/\s+/g, " ")
        .trim(),
    ).toBe("DocType/Walk Order");
  });
});
