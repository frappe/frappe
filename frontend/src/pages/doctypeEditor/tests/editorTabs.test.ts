// The Editor / Settings / Preview strip: one tab per EDITOR_TABS entry with its icon; a click performs editor.open_tab.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";

import { acts } from "@/acts/dispatcher";
import EditorTabs from "../EditorTabs.vue";
import type { EditorTab } from "../pendingEdits";

const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

describe("the editor tab strip", () => {
  const perform = vi.spyOn(acts, "perform").mockResolvedValue(undefined as never);

  it("draws the three tabs with an icon each and performs editor.open_tab on click", async () => {
    const tab = ref<EditorTab>("editor");
    const root = document.createElement("div");
    document.body.appendChild(root);
    const app = createApp({
      render: () =>
        h(EditorTabs, {
          modelValue: tab.value,
        }),
    });
    app.mount(root);
    apps.push(app);
    await nextTick();

    const tabs = [...root.querySelectorAll<HTMLElement>("[role='tab']")];
    expect(tabs.map((t) => t.textContent?.trim())).toEqual([
      "Editor",
      "Settings",
      "Preview",
    ]);
    for (const icon of ["layout-list", "settings", "eye"])
      expect(root.querySelector(`.lucide-${icon}`)).not.toBeNull();

    tabs[1].dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    tabs[1].click();
    await nextTick();
    expect(perform).toHaveBeenCalledWith("editor.open_tab", "settings");
    expect(root.querySelector("[data-act]")?.getAttribute("data-act")).toBe("editor.open_tab");
  });
});
