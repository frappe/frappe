import type { Component } from "vue";
import type { Router } from "vue-router";
import type { ActFields } from "@/acts/dispatcher";
import type { PageDialog } from "@/shell/dialogs/types";

/** Where an added or moved item lands; absent or unknown anchors append. */
export type Position = { before?: string; after?: string };

export interface SurfaceItem {
  name: string;
  label?: string;
  icon?: string;
  [key: string]: any;
}

/** The keys every act item adds to its surface's list. */
export const ACT_KEYS: readonly string[] = ["key", "right", "palette", "argument", "when"];

/** Which half of the header row an item sits in; omitted means `right`. */
export type HeaderZone = "left" | "right";

// Unnamed, the page is `any`, so the engine draws any page's items.
/**
 * One item of the header row: a crumb, a button, a menu entry or `Save`. A `dropdown`
 * or a `section` is a container: its members point at it with `group`, two deep.
 */
export interface HeaderItem<Page extends PageApi = any> extends SurfaceItem, ActFields<Page> {
  label: string;
  zone?: HeaderZone;
  /** Omitted: an entry in `⋯` on the right, a button on the left. */
  display?: "button" | "dropdown" | "section" | "crumb";
  /** The container this sits in; an undeclared name gets an anonymous one inside `⋯`. */
  group?: string;
  /** A path this item links to; `run` wins when both are given. */
  href?: string;
  run?: (page: Page, value?: any) => any;
  /** Draws the item itself, as a control in either zone; `display` and `group` then do nothing. */
  component?: Component;
  /** Forwarded to whatever draws the item, filtered to its declared props; a `component`'s are not filtered. */
  props?: Record<string, any>;
}

export const HEADER_ITEM_KEYS: readonly string[] = [
  "name",
  "label",
  "icon",
  "zone",
  "display",
  "group",
  "href",
  "run",
  "component",
  "props",
  ...ACT_KEYS,
];

/** One item of the frame's column: a band a script adds, or one of the two built-in regions. */
export interface FrameItem extends SurfaceItem {
  /** Draws the band; absent on a built-in, which the host draws itself. */
  component?: Component;
  props?: Record<string, any>;
  /** Whether the band's wrapper takes the page's side padding; omitted means it does. */
  gutter?: boolean;
}

export const FRAME_ITEM_KEYS: readonly string[] = ["name", "component", "props", "gutter"];

/** One column of the body row: a built-in (`form`, `panel`) or one a script adds. */
export interface BodyItem extends SurfaceItem {
  /** Draws the column; absent on a built-in, which the host draws itself. */
  component?: Component;
  props?: Record<string, any>;
  /** Whether the column's content takes the page's side padding; omitted means it does. */
  gutter?: boolean;
  /** Absent, the column flexes and shares the rest with the other flex columns. */
  width?: number;
  minWidth?: number;
  maxWidth?: number;
  /** The reader can shut the column to a strip; its component then receives `collapsed`. */
  collapsible?: boolean;
}

export const BODY_ITEM_KEYS: readonly string[] = [
  "name",
  "component",
  "props",
  "gutter",
  "width",
  "minWidth",
  "maxWidth",
  "collapsible",
];

export interface SurfaceVerbs<Item extends SurfaceItem = SurfaceItem> {
  /** One item, or a block that splices as a unit at the anchor, in list order. */
  add(item: Item | Item[], position?: Position): void;
  hide(name: string): void;
  show(name: string): void;
  update(name: string, patch: Partial<Item>): void;
  move(name: string, position: Position): void;
  has(name: string): boolean;
  order(names: string[]): void;
  /** Hides every item present at the call; a later `add` draws, a later `show(name)` brings one back. */
  clear(): void;
}

export interface PageToast {
  success(message: string): void;
  error(message: string): void;
  info(message: string): void;
}

export type {
  PageDialogField,
  PageDialogColumn,
  PageDialogSection,
  PageDialogTab,
  PageDialogActionContext,
  PageDialogAction,
  PageDialogFormOptions,
  PageDialogOpenOptions,
  PageDialogControl,
  PageDialogConfirmAction,
  PageDialogConfirmOptions,
  PageDialogDangerOptions,
  PageDialog,
} from "@/shell/dialogs/types";

/** One source's handler for an event: it receives `page`, and the event's detail when it has one. */
export type Handler = (page: any, detail?: any) => any;

/** One source's handlers, as a page's sources hand them to the engine in run order. */
export interface Registration {
  source: string;
  handlers: Record<string, Handler>;
}

/** What every page built on the engine hands its handlers; a page adds its own members. */
export interface PageApi {
  doctype: string;
  meta: Record<string, any> | null;
  /** Every right frappe would check for this doctype, valued `0` or `1`. */
  perms: Record<string, any>;
  /** The session user's roles, resolved before any handler runs. */
  roles: string[];
  /** The column itself: the built-in `header` and `body`, and a script's bands around them. */
  frame: SurfaceVerbs<FrameItem>;
  header: SurfaceVerbs<HeaderItem>;
  /** The body row as one list: the built-in `form` and `panel`, and a script's columns around them. */
  body: SurfaceVerbs<BodyItem>;
  refresh(): Promise<void>;
  toast: PageToast;
  dialog: PageDialog;
  call(method: string, params?: Record<string, any>): Promise<any>;
  /** Server data for `onRefresh`: the value kept for `key`, fetched once per visit; undefined until a fetch lands. */
  cached<T>(key: string, fetch: () => Promise<T> | T): T | undefined;
  router: Router;
}
