// The Record page customization API: what a script's handlers receive and the
// item schemas the four surfaces accept.
import type { Component } from "vue";
import type { Router } from "vue-router";

/** Where an added or moved item lands; absent or unknown anchors append. */
export type Position = { before?: string; after?: string };

export interface SurfaceItem {
  name: string;
  label?: string;
  icon?: string;
  [key: string]: any;
}

export interface QuickAction extends SurfaceItem {
  label: string;
  description?: string;
  run?: (page: RecordPageApi) => any;
}

export interface HeaderAction extends SurfaceItem {
  label: string;
  /** The menu band this action joins; omitted means `actions`. */
  group?: string;
  run?: (page: RecordPageApi) => any;
}

export interface TabCreateAction {
  label: string;
  icon: string;
  run: (page: RecordPageApi) => any;
}

export interface TabItem extends SurfaceItem {
  label: string;
  component?: Component;
  props?: Record<string, any>;
  /** Joins the composer's `+` menu while this tab is on the strip. */
  create?: TabCreateAction;
}

export interface PanelSectionItem extends SurfaceItem {
  component?: Component;
  props?: Record<string, any>;
  opened?: boolean;
}

export interface SurfaceVerbs<Item extends SurfaceItem = SurfaceItem> {
  add(item: Item, position?: Position): void;
  hide(name: string): void;
  show(name: string): void;
  update(name: string, patch: Partial<Item>): void;
  move(name: string, position: Position): void;
  has(name: string): boolean;
  order(names: string[]): void;
}

/** The tabs surface also tells a handler which tab the reader is on. */
export interface TabsApi extends SurfaceVerbs<TabItem> {
  readonly active: string;
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
  [key: string]: any;
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
  /** Renders the doctype's `Quick Entry` Form Layout, meta-derived if none. */
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

/**
 * The dialog capability. Every verb resolves `null` when the reader dismissed
 * the dialog — by Esc, the backdrop, the close button, or by navigating off the
 * record — so `if (!result) return` is the idiom. Un-awaited promises are
 * ignored: fire-and-forget stays legal.
 */
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
  confirm(args: Record<string, any>): Promise<true | null>;
  /** `confirm` in red, labelled Delete by default. */
  danger(args: Record<string, any>): Promise<true | null>;
}

/** The curated object every handler mutates — a script's whole capability surface. */
export interface RecordPageApi {
  doctype: string;
  docname: string;
  doc: Record<string, any>;
  meta: Record<string, any> | null;
  perms: Record<string, any>;
  isDirty: boolean;
  quickActions: SurfaceVerbs<QuickAction>;
  headerActions: SurfaceVerbs<HeaderAction>;
  tabs: TabsApi;
  panelSections: SurfaceVerbs<PanelSectionItem>;
  save(): Promise<void>;
  reload(): Promise<void>;
  refresh(): Promise<void>;
  toast: PageToast;
  dialog: PageDialog;
  call(method: string, params?: Record<string, any>): Promise<any>;
  router: Router;
}

export type Handler = (page: RecordPageApi) => any;

/** What a script evaluates to: named event handlers, each receiving `page`. */
export type RecordPageHandlers = Record<string, Handler>;
