// The palette's "Go to tab" rows: one per tab on the strip, gone with the page.
import { describe, expect, it, vi } from "vitest";

import type { RecordPageController } from "@/recordPage";
import { Surface } from "@/pageEngine/surface";
import { TAB_ITEM_KEYS, type TabItem } from "@/recordPage/types";
import { pageRows } from "@/shell/palette";
import { registerTabRows } from "../tabRows";

describe("registerTabRows", () => {
  it("lists a row per tab on the strip, moves the reader to it, and goes when let go", () => {
    const tabs = new Surface<TabItem>({ surface: "tabs", keys: TAB_ITEM_KEYS });
    tabs.add([
      { name: "calls", label: "Calls", icon: "lucide-phone" },
      { name: "notes", label: "Notes" },
    ]);
    tabs.hide("notes");
    const activate = vi.fn();
    const release = registerTabRows({ tabs, page: { tabs: { activate } } } as unknown as RecordPageController);

    const rows = pageRows();
    expect(rows.map(({ id, label, icon }) => ({ id, label, icon }))).toEqual([
      { id: "tab:calls", label: "Go to tab: Calls", icon: "lucide-phone" },
    ]);
    rows[0].run();
    expect(activate).toHaveBeenCalledWith("calls");

    release();
    expect(pageRows()).toEqual([]);
  });
});
