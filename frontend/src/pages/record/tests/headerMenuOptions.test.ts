// The projected rows in frappe-ui's Menu vocabulary: what runs, what links, what nests.
import { describe, expect, it, vi } from "vitest";
import type { HeaderItem, HeaderNode } from "@/recordPage";
import { bandRows, menuContent } from "../headerMenuOptions";

function node(item: Partial<HeaderItem> & { name: string }, members: HeaderNode[] = []): HeaderNode {
  const container = item.display === "dropdown" || item.display === "section" ? item.display : undefined;
  return { item: { label: item.name, ...item }, container, members };
}

describe("menuContent", () => {
  it("gives a plain item an onClick that runs it", () => {
    const run = vi.fn();
    const item = node({ name: "copy_ref", run: () => {} });
    const [row] = menuContent([item], run);
    row.onClick();
    expect(run).toHaveBeenCalledWith(item.item);
    expect(row.route).toBeUndefined();
  });

  it("gives an item with only an href a route, and no onClick", () => {
    const [row] = menuContent([node({ name: "parent", href: "/crm-organization" })], vi.fn());
    expect(row).toEqual({ label: "parent", icon: undefined, route: "/crm-organization" });
  });

  it("lets run win over href", () => {
    const [row] = menuContent([node({ name: "both", href: "/x", run: () => {} })], vi.fn());
    expect(row.route).toBeUndefined();
    expect(row.onClick).toBeTypeOf("function");
  });

  it("renders a section as a group and a dropdown as a submenu", () => {
    const rows = menuContent(
      [
        node({ name: "danger", label: "Danger", display: "section" }, [node({ name: "wipe" })]),
        node({ name: "tools", label: "Tools", display: "dropdown" }, [node({ name: "audit" })]),
      ],
      vi.fn()
    );
    expect(rows[0]).toMatchObject({ group: "Danger", options: [{ label: "wipe" }] });
    expect(rows[1]).toMatchObject({ label: "Tools", submenu: [{ label: "audit" }] });
  });

  it("bandRows never nests a group", () => {
    const rows = bandRows([node({ name: "one" }), node({ name: "two", href: "/two" })], vi.fn());
    expect(rows.map((row) => row.group)).toEqual([undefined, undefined]);
    expect(rows[1].route).toBe("/two");
  });
});
