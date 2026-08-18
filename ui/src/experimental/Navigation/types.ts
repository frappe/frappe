import type { SavedView } from "../SavedViews/types";
import type { NavigationItemKind } from "./itemKinds";

export interface NavigationScope {
  app: string;
  doctype: string;
}

export const DEFAULT_APP = "frappe";

export type NavigationItemType = "view" | "doctype" | "link" | (string & {});

export interface NavigationItem {
  name: string;
  type: NavigationItemType;
  label: string;
  icon: string;
  dt: string;
  url: string;
  new_tab: 0 | 1;
  hidden: 0 | 1;
  own: 0 | 1;
  view: SavedView | null;
}

export interface NavigationSection {
  name: string;
  label: string;
  user: string;
  hidden: 0 | 1;
  items: NavigationItem[];
}

export type NavigationItemValues = Record<string, string>;

export interface NavigationItemNaming {
  label: string;
  icon: string;
}

export interface ArrangedRow {
  name: string;
  hidden: 0 | 1;
}

export interface DragChange {
  moved?: { element: NavigationItem; newIndex: number };
  added?: { element: NavigationItem; newIndex: number };
  removed?: { element: NavigationItem };
}

export interface SidebarResponse {
  sections: NavigationSection[];
  can_manage_shared: boolean;
  default_view: string | number | null;
  default_view_is_stored: boolean;
}

export type ViewCounts = Record<string, number | null>;

export interface AddMenuItem {
  label: string;
  icon?: string;
  slots?: Record<string, unknown>;
  onClick: () => void;
}

export interface AddMenuGroup {
  group: string;
  items: AddMenuItem[];
}

export interface AddMenuOptions {
  items?: AddMenuItem[];
  groups?: AddMenuGroup[];
}

export interface PoolView {
  name: string | number;
  label: string;
  icon?: string;
  user?: string;
}

export interface NavigationSidebarProps {
  doctype: string;
  itemKinds?: NavigationItemKind[];
  app?: string;
  activeView?: string | number | null;
  basePath?: string;
}
