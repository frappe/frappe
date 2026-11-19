import { describe, expect, it, vi } from "vitest";
import { startValues, missing, buildRow } from "../addTypes";
import {
  fetchViews,
  type ListedView,
  pickableViews,
  viewKeyOf,
  viewRow,
} from "../viewPicker";

const runMethod = vi.hoisted(() => vi.fn());
vi.mock("@framework/ui/api", () => ({ runMethod }));

const views: ListedView[] = [
  { key: "list", label: "List", type: "List", layer: null },
  { key: "cards", label: "Cards", type: "Cards", layer: null },
  { key: "mine", label: "Mine", type: "List", layer: "own" },
  { key: "team", label: "Team", type: "List", layer: "site" },
  { key: "app-board", label: "Board", type: "Kanban", layer: "app" },
];
const types = [
  { name: "List", label: "List", icon: "list" },
  { name: "Cards", label: "Cards", icon: null },
  { name: "Kanban", label: "Kanban", icon: "kanban" },
];

describe("the View step", () => {
  it("lists every view under Just me, in the order the server gave", () => {
    expect(pickableViews(views, "user").map((view) => view.key)).toEqual([
      "list",
      "cards",
      "mine",
      "team",
      "app-board",
    ]);
  });

  it("hides an own view under Everyone", () => {
    expect(pickableViews(views, "site").map((view) => view.key)).toEqual([
      "list",
      "cards",
      "team",
      "app-board",
    ]);
  });

  it("reads the views of one doctype for the app", async () => {
    runMethod.mockResolvedValue({ data: { ToDo: views } });
    expect(await fetchViews("ToDo", "crm")).toEqual(views);
    expect(runMethod).toHaveBeenCalledWith(
      "frappe.desk.doctype.doctype_view.api.list_views",
      { doctype: "ToDo", app: "crm" },
      { http: "GET" }
    );
    runMethod.mockResolvedValue({ data: {} });
    expect(await fetchViews("ToDo", "crm")).toEqual([]);
  });

  it("writes the DocType link, the view key, its label and its type's icon", () => {
    expect(viewRow("ToDo", views[4], types)).toEqual({
      item_type: "View",
      link_doctype: "DocType",
      link_to: "ToDo",
      payload: { view: "app-board" },
      label: "Board",
      icon: "kanban",
    });
  });

  it("leaves the icon out when the view type has none", () => {
    expect(viewRow("ToDo", views[1], types)).not.toHaveProperty("icon");
  });

  it("asks for the doctype, then the view, before it adds", () => {
    expect(missing("View", startValues())?.field).toBe("doctype");
    expect(missing("View", { ...startValues(), doctype: "ToDo" })?.field).toBe(
      "view"
    );
    const values = { ...startValues(), doctype: "ToDo", view: "team" };
    expect(missing("View", values)).toBeNull();
    expect(buildRow("View", values, { listed: views[3], types })).toMatchObject(
      {
        link_to: "ToDo",
        payload: { view: "team" },
      }
    );
  });

  it("reads the view key of a row", () => {
    expect(
      viewKeyOf({ key: "k", item_type: "View", payload: { view: "team" } })
    ).toBe("team");
    expect(viewKeyOf({ key: "k", item_type: "View" })).toBe("");
  });
});
