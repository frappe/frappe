// What every page built on the engine shares: the base `page`, the surface verbs and
// the item schemas of the three built-in lists.
import type { Component } from "vue";
import type { Router } from "vue-router";
import type { ActFields } from "@/acts/dispatcher";

/** Where an added or moved item lands; absent or unknown anchors append. */
export type Position = { before?: string; after?: string };

export interface SurfaceItem {
  name: string;
  label?: string;
  icon?: string;
  [key: string]: any;
}

/** The keys every act item adds to its surface's list. */
export const ACT_KEYS: readonly string[] = ["key", "right", "palette", "argument"];

/** Which half of the header row an item sits in; omitted means `right`. */
export type HeaderZone = "left" | "right";

/**
 * One item of the header row: a crumb, a button, a menu entry or `Save`. A `dropdown`
 * or a `section` is a container: its members point at it with `group`, two deep.
 */
// Unnamed, the page is `any`, so the engine draws any page's items.
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
}

/** A field as a script writes it: DocField vocabulary, not `FieldMeta`'s camelCase. */
export interface PageDialogField {
  fieldname: string;
  fieldtype: string;
  label?: string;
  /** Link target, or a `Select`'s newline-separated choices. */
  options?: string;
  reqd?: boolean | 0 | 1;
  read_only?: boolean | 0 | 1;
  hidden?: boolean | 0 | 1;
  depends_on?: string;
  mandatory_depends_on?: string;
  read_only_depends_on?: string;
  description?: string;
  /** Closed on purpose: it agrees with `PageFieldPatch` on what a script may write. */
}

/** One column of a `tabs` layout; its fields are written, not named. */
export interface PageDialogColumn {
  name?: string;
  label?: string;
  fields: PageDialogField[];
}

export interface PageDialogSection {
  name?: string;
  label?: string;
  hideLabel?: boolean;
  hideBorder?: boolean;
  collapsible?: boolean;
  opened?: boolean;
  depends_on?: string;
  columns: PageDialogColumn[];
}

export interface PageDialogTab {
  name?: string;
  label?: string;
  depends_on?: string;
  sections: PageDialogSection[];
}

/** What a custom `form` action's `onClick` receives. */
export interface PageDialogActionContext {
  /** The dialog's current values, keyed by fieldname. */
  data: Record<string, any>;
  /** Closes the dialog, resolving the opener's promise with `result`. */
  close: (result?: any) => void;
  /** Runs the mandatory-field check; false leaves the errors on screen. */
  validate: () => boolean;
}

export interface PageDialogAction {
  label: string;
  variant?: string;
  theme?: string;
  icon?: string;
  /** Omitted means the default: validate, then close with the form's data. */
  onClick?: (context: PageDialogActionContext) => any;
}

/**
 * `page.dialog.form()`'s options. Exactly one layout mode may be given —
 * `fields`, `tabs`, or `doctype` (optionally narrowed by `fieldnames`).
 */
export interface PageDialogFormOptions {
  title?: string;
  /** Flat field list, wrapped in one unlabelled section. */
  fields?: PageDialogField[];
  /** Full `tabs > sections > columns > fields` layout. */
  tabs?: PageDialogTab[];
  /** With `fieldnames`: those fields, in that order, straight from the doctype's meta. */
  doctype?: string;
  /** With `doctype`: only these fields, in this order. */
  fieldnames?: string[];
  defaults?: Record<string, any>;
  /** Fieldnames forced mandatory, whatever the layout says. */
  required?: string[];
  size?: string;
  /** Custom buttons; when given, Submit and `onSubmit` are not rendered. */
  actions?: PageDialogAction[];
  /** Runs on Submit after validation; throwing keeps the dialog open. */
  onSubmit?: (data: Record<string, any>) => any;
  onCancel?: () => any;
  submitLabel?: string;
  cancelLabel?: string;
  dismissible?: boolean;
}

/** Chrome for `open()`'s host dialog; the component renders the body. */
export interface PageDialogOpenOptions {
  title?: string;
  size?: string;
  dismissible?: boolean;
}

/** What a `confirm`/`danger` callback receives: the engine's own object, not frappe-ui's. */
export interface PageDialogControl {
  /** Closes the dialog; the verb's promise settles from the verb, as ever. */
  close(): void;
  /** Shows an inline error and re-enables the buttons; `null` clears it. */
  setError(message: string | null): void;
}

/** One button on a `confirm`/`danger` — the five props `page` forwards. */
export interface PageDialogConfirmAction {
  label: string;
  variant?: string;
  theme?: string;
  icon?: string;
  /** Omitted means the button only dismisses, and the verb resolves `null`. */
  onClick?: (control: PageDialogControl) => any;
}

/** `confirm`'s options; a key not named here is dropped, not forwarded. */
export interface PageDialogConfirmOptions {
  title?: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  theme?: string;
  icon?: string;
  size?: string;
  dismissible?: boolean;
  onConfirm?: (control: PageDialogControl) => any;
  onCancel?: () => any;
  /** Custom buttons; when given, the confirm/cancel pair is not rendered. */
  actions?: PageDialogConfirmAction[];
}

/** `danger` forces red and its own icon, so it names neither. */
export type PageDialogDangerOptions = Omit<
  PageDialogConfirmOptions,
  "theme" | "icon"
>;

/** The dialog capability. Every verb resolves `null` on dismissal, so `if (!result) return` is the idiom. */
export interface PageDialog {
  /** Renders `component` in a dialog, passing it a `close(result)` prop. */
  open(
    component: Component,
    props?: Record<string, any>,
    options?: PageDialogOpenOptions,
  ): Promise<any>;
  /** The declarative tier: resolves `{fieldname: value}` on submit. */
  form(options: PageDialogFormOptions): Promise<Record<string, any> | null>;
  /** Resolves `true` when confirmed. */
  confirm(options: PageDialogConfirmOptions): Promise<true | null>;
  /** `confirm` in red, labelled Delete by default. */
  danger(options: PageDialogDangerOptions): Promise<true | null>;
}

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
