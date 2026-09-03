// The Record page customization API: what a script's handlers receive and the
// item schemas the four surfaces accept.
import type { Component } from "vue";
import type { Router } from "vue-router";
import type { FieldAccess } from "@framework/ui/composables/useDocPermissions";

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

/**
 * An action in the record's header. A `dropdown` or a `section` is a container:
 * its members point at it with `group`, and containers nest two deep.
 */
export interface HeaderAction extends SurfaceItem {
  label: string;
  display?: "button" | "dropdown" | "section";
  /** The container this sits in; an undeclared name gets an anonymous one inside `⋯`. */
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
  /** One item, or a block that splices as a unit at the anchor, in list order. */
  add(item: Item | Item[], position?: Position): void;
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
  /**
   * Moves the reader to a tab on this strip. Resolved at the call, never queued,
   * and `active` still reads the old tab on the next line: read it in the next handler.
   */
  activate(name: string): void;
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

/**
 * What a script may override on one of the record's fields, spelled as a
 * DocField spells it. Closed: a key not named here is dropped with a dev warning.
 */
export interface PageFieldPatch {
  // `0 | 1` alongside the boolean: a DocField spells these as ints.
  hidden?: boolean | 0 | 1;
  read_only?: boolean | 0 | 1;
  reqd?: boolean | 0 | 1;
  label?: string;
  placeholder?: string;
  description?: string;
  /** Link target, or a `Select`'s newline-separated choices. */
  options?: string;
  /** Search filters for a `Link` field. v1 spells it this way; so do we. */
  link_filters?: Record<string, unknown>;
  /** Decimal places for a numeric field. */
  precision?: number | string;
  /** Renders this component in the field's slot instead of the default one. */
  component?: Component;
  /** Props bound onto whichever component renders the field. */
  props?: Record<string, any>;
}

/** What `get` hands back: the keys `update` writes, resolved, plus the two that identify the field. */
export interface PageField extends PageFieldPatch {
  fieldname: string;
  fieldtype: string;
  // Resolved, so these are answered as booleans however they were written.
  hidden?: boolean;
  read_only?: boolean;
  reqd?: boolean;
}

/**
 * The fields surface: a render-time overlay on fields authored elsewhere, cleared
 * before every replay. No `add`, `move` or `order`; ordering is the Form Layout's job.
 */
export interface PageFields {
  hide(fieldname: string): void;
  show(fieldname: string): void;
  update(fieldname: string, patch: PageFieldPatch): void;
  /** Whether the doctype has this field at all. */
  has(fieldname: string): boolean;
  /** The field as it currently resolves — post-override, post-`depends_on`. */
  get(fieldname: string): PageField | null;
}

/** What a script may override on one of the Form Layout's tabs. */
export interface PageFormTabPatch {
  label?: string;
}

/** What `page.formTabs.get()` hands back: the tab as the strip resolves it. */
export interface PageFormTab {
  /** What the author wrote, if anything; the address is `identity`. */
  name?: string;
  identity: string;
  label: string;
  /** Resolved: `depends_on` and this surface's own ops both folded in. */
  hidden: boolean;
}

/**
 * The Form Layout's own tab strip, inside the Details form. A tab is addressed
 * by its identity (`name`, else the slugified label, else its position), never by label.
 */
export interface PageFormTabs {
  hide(identity: string): void;
  show(identity: string): void;
  update(identity: string, patch: PageFormTabPatch): void;
  /** Whether the layout carries this tab at all, on screen or not. */
  has(identity: string): boolean;
  /** The tab as it currently resolves — post-override, post-`depends_on`. */
  get(identity: string): PageFormTab | null;
  /** The identity of the tab the reader is on, or `''` outside the form; not a name. */
  readonly active: string;
  /** Moves the reader to a tab of the form, on `TabsApi.activate`'s terms. */
  activate(identity: string): void;
}

/**
 * A child row as a script addresses it: re-finds its row on every access, with
 * fields read and written bare. Access to a removed row throws.
 */
export interface PageRow {
  /** Fires this row's handler for one child field: `row.trigger('rate')` dispatches `'products.rate'`. */
  trigger(fieldname: string): Promise<void>;
  [fieldname: string]: any;
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

/** The curated object every handler mutates — a script's whole capability surface. */
export interface RecordPageApi {
  doctype: string;
  docname: string;
  doc: Record<string, any>;
  /** The document as the server last showed it; read-only, `page.doc` is the draft. */
  saved: Record<string, any>;
  meta: Record<string, any> | null;
  /** Every right frappe would check for this doctype, valued `0` or `1`. */
  perms: Record<string, any>;
  /** The session user's roles, resolved before any handler runs. */
  roles: string[];
  /** What this user may do with a field, by permlevel; an unknown one is `none`. */
  fieldAccess(fieldname: string): FieldAccess;
  isDirty: boolean;
  quickActions: SurfaceVerbs<QuickAction>;
  headerActions: SurfaceVerbs<HeaderAction>;
  tabs: TabsApi;
  panelSections: SurfaceVerbs<PanelSectionItem>;
  fields: PageFields;
  /** The Form Layout's own tab strip, inside the Details form. */
  formTabs: PageFormTabs;
  /** The child table's rows as handles, in array order; a non-table fieldname answers empty. */
  rows(parentfield: string): PageRow[];
  save(): Promise<void>;
  reload(): Promise<void>;
  refresh(): Promise<void>;
  toast: PageToast;
  dialog: PageDialog;
  call(method: string, params?: Record<string, any>): Promise<any>;
  router: Router;
}

export type { FieldAccess };

/**
 * A top-level key receives `(page)`; one nested under a child table receives
 * `(page, row)`, except `onRemove`, whose row is gone.
 */
export type Handler = (page: RecordPageApi, row?: PageRow) => any;

/** What an author writes: event handlers, plus a block nested under a child table's fieldname. */
export type AuthoredHandlers = Record<
  string,
  Handler | Record<string, Handler>
>;

/** What the engine dispatches against: nested blocks flattened onto dotted keys. */
export type RecordPageHandlers = Record<string, Handler>;
