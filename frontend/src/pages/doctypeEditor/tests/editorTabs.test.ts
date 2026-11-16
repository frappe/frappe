// The Editor / Settings / Preview strip: one tab per EDITOR_TABS entry with its icon, v-model switches.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";

import EditorTabs from "../EditorTabs.vue";
import type { EditorTab } from "../pendingEdits";

const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

describe("the editor tab strip", () => {
  it("draws the three tabs with an icon each and switches the model on click", async () => {
    const tab = ref<EditorTab>("editor");
    const root = document.createElement("div");
    document.body.appendChild(root);
    const app = createApp({
      render: () =>
        h(EditorTabs, {
          modelValue: tab.value,
          "onUpdate:modelValue": (v: EditorTab) => (tab.value = v),
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
    expect(tab.value).toBe("settings");
  });
});
