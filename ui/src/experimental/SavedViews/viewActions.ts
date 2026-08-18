import type { SavedView } from "./types";

export type ViewActionKind =
  | "edit"
  | "duplicate"
  | "setDefault"
  | "makeShared"
  | "makePersonal"
  | "removeFromSidebar"
  | "delete";

export interface ViewAction {
  kind: ViewActionKind;
  label: string;
  icon: string;
  danger?: boolean;
}

export function getViewActions(
  view: SavedView,
  canManageShared: boolean,
  isStoredDefault = false
): ViewAction[] {
  if (!view.name) return [];

  const isShared = !view.user;
  const canEdit = canEditView(view, canManageShared);

  const actions: ViewAction[] = [];

  if (canEdit) actions.push({ kind: "edit", label: "Edit", icon: "edit-2" });

  actions.push({ kind: "duplicate", label: "Duplicate", icon: "copy" });
  if (!isStoredDefault)
    actions.push({ kind: "setDefault", label: "Set as default", icon: "star" });

  if (canManageShared) actions.push(moveAction(isShared));

  if (canEdit) {
    actions.push({
      kind: "removeFromSidebar",
      label: "Remove from sidebar",
      icon: "minus-circle",
    });
    actions.push({
      kind: "delete",
      label: "Delete",
      icon: "trash-2",
      danger: true,
    });
  }

  return actions;
}

export function canEditView(view: SavedView, canManageShared: boolean): boolean {
  return Boolean(view.name) && (Boolean(view.user) || canManageShared);
}

function moveAction(isShared: boolean): ViewAction {
  return isShared
    ? { kind: "makePersonal", label: "Make personal", icon: "lock" }
    : { kind: "makeShared", label: "Share with everyone", icon: "users" };
}
