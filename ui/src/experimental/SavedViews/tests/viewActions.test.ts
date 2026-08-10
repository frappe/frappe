import { describe, expect, it } from "vitest";
import { getViewActions } from "../viewActions";
import type { SavedView } from "../types";

const SHARED: SavedView = {
  name: "1",
  label: "Open",
  reference_doctype: "Note",
  type: "list",
  user: "",
};

const PERSONAL: SavedView = { ...SHARED, user: "member@example.com" };

function kinds(
  view: SavedView,
  canManageShared: boolean,
  isStoredDefault = false
) {
  return getViewActions(view, canManageShared, isStoredDefault).map(
    (action) => action.kind
  );
}

describe("getViewActions", () => {
  it("offers a member everything on their own view except crossing into shared", () => {
    expect(kinds(PERSONAL, false)).toEqual([
      "edit",
      "duplicate",
      "setDefault",
      "removeFromSidebar",
      "delete",
    ]);
  });

  it("offers a member only the read-safe actions on a shared view", () => {
    expect(kinds(SHARED, false)).toEqual(["duplicate", "setDefault"]);
  });

  it("drops 'Set as default' on the view that is already the stored default", () => {
    expect(kinds(PERSONAL, false, true)).not.toContain("setDefault");
    expect(kinds(SHARED, false, true)).toEqual(["duplicate"]);
  });

  it("keeps 'Set as default' on the stand-in the list merely opens with", () => {
    expect(kinds(SHARED, false, false)).toContain("setDefault");
  });

  it("lets a manager edit and unshare a shared view", () => {
    expect(kinds(SHARED, true)).toContain("edit");
    expect(kinds(SHARED, true)).toContain("makePersonal");
    expect(kinds(SHARED, true)).toContain("delete");
  });

  it("lets a manager share one of their personal views", () => {
    expect(kinds(PERSONAL, true)).toContain("makeShared");
    expect(kinds(PERSONAL, true)).not.toContain("makePersonal");
  });

  it("never offers a view both directions of the same move", () => {
    const shared = kinds(SHARED, true);

    expect(shared).toContain("makePersonal");
    expect(shared).not.toContain("makeShared");
  });

  it("marks deletion as the destructive action", () => {
    const remove = getViewActions(PERSONAL, false).find(
      (action) => action.kind === "delete"
    );

    expect(remove?.danger).toBe(true);
  });

  it("gives every action a label to render", () => {
    const actions = getViewActions(SHARED, true);

    expect(actions.every((action) => Boolean(action.label))).toBe(true);
  });
});
