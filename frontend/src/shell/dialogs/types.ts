import type { Component } from "vue";
import type {
  DialogConfirmAction,
  DialogConfirmOptions,
  DialogControl,
  DialogDangerOptions,
} from "@/narrowedDialog";

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
  /** A table field's child columns, in a doctype field's vocabulary: a Table MultiSelect needs the Link column it picks by. */
  child_fields?: PageDialogField[];
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

export type PageDialogControl = DialogControl;
export type PageDialogConfirmAction = DialogConfirmAction;
export type PageDialogConfirmOptions = DialogConfirmOptions;
export type PageDialogDangerOptions = DialogDangerOptions;

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
