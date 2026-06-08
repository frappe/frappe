import type { Component } from "vue";
import { setScoped } from "./scopedRegistry";
import AutocompleteField from "./fields/AutocompleteField.vue";
import CheckField from "./fields/CheckField.vue";
import DateField from "./fields/DateField.vue";
import DatetimeField from "./fields/DatetimeField.vue";
import DurationField from "./fields/DurationField.vue";
import DynamicLinkField from "./fields/DynamicLinkField.vue";
import HeadingField from "./fields/HeadingField.vue";
import HtmlField from "./fields/HtmlField.vue";
import LinkField from "./fields/LinkField.vue";
import NumberField from "./fields/NumberField.vue";
import PasswordField from "./fields/PasswordField.vue";
import PhoneField from "./fields/PhoneField.vue";
import RatingField from "./fields/RatingField.vue";
import SelectField from "./fields/SelectField.vue";
import TableField from "./fields/TableField.vue";
import TextField from "./fields/TextField.vue";
import TextareaField from "./fields/TextareaField.vue";
import TimeField from "./fields/TimeField.vue";

/** Process-global fieldtype → component registry. */
const registry = new Map<string, Component>();

const FALLBACK = "__fallback__";

export interface RegisterFieldTypeOptions {
  /**
   * `true` (default): register **globally** for the process — the registration
   * persists until overwritten. This is how apps install their fields once at
   * startup.
   *
   * `false`: register **scoped** to the current Vue effect scope (a component's
   * `setup`). The previous mapping is snapshotted and **automatically restored**
   * when that scope is disposed (the component unmounts). Use this for an override
   * that must not leak to the rest of the app — e.g. a story/demo, or a screen
   * that swaps a field only while it is open. Must be called synchronously in
   * `setup` (so it is in place before child fields render); if there is no active
   * scope to tie cleanup to, it falls back to a global registration and warns.
   */
  global?: boolean;
}

export function registerFieldType(
  fieldtype: string,
  component: Component,
  options: RegisterFieldTypeOptions = {}
): void {
  const { global = true } = options;

  // Scoped: snapshot + auto-restore on the current component's unmount.
  if (!global && setScoped(registry, fieldtype, component)) return;

  if (!global) {
    console.warn(
      `[FormLayout] registerFieldType('${fieldtype}', …, { global: false }) was ` +
        `called outside a Vue effect scope (component setup), so there is nothing ` +
        `to auto-revert on. Registered globally instead.`
    );
  }
  registry.set(fieldtype, component);
}

export function getFieldComponent(fieldtype: string): Component {
  return registry.get(fieldtype) ?? registry.get(FALLBACK)!;
}

registerFieldType("Link", LinkField);
registerFieldType("Select", SelectField);
registerFieldType("Check", CheckField);
registerFieldType("Date", DateField);
registerFieldType("Datetime", DatetimeField);
registerFieldType("Time", TimeField);

// One numeric control for all number types; it formats per fieldtype (locale
// grouping, precision, currency symbol, percent) with lib defaults. Apps wanting
// site-accurate settings register their own field (see formatNumber.ts).
for (const t of ["Int", "Float", "Currency", "Percent"]) {
  registerFieldType(t, NumberField);
}

// One textarea for the multi-line text types. `JSON`, `Markdown Editor`, and
// `HTML Editor` ride along here for now: frappe-ui ships no code-editor primitive,
// so all of these (plus `Code`) stay on a plain textarea until the shared
// `CodeEditorField` (Ace, mode from `field.options`) is built — see
// plans/fieldtypes-remaining.md.
for (const t of [
  "Small Text",
  "Text",
  "Long Text",
  "Code",
  "JSON",
  "Markdown Editor",
  "HTML Editor",
]) {
  registerFieldType(t, TextareaField);
}

// `Phone` → minimal `type=tel` input (raw-string value; ISD picker is a later
// upgrade). `Heading`/`HTML` are display-only (no value, no emit).
registerFieldType("Phone", PhoneField);
registerFieldType("Heading", HeadingField);
registerFieldType("HTML", HtmlField);

registerFieldType("Password", PasswordField);

// Pickers / selectors with a frappe-ui (or built) control.
//   - `Autocomplete` → `Combobox`, options from `field.options`.
//   - `Rating` → `Rating`, 0..1 fraction ⇄ stars (`field.options` = star count).
//   - `Duration` → `Duration` (v-model is the seconds value the doc stores).
//   - `Dynamic Link` → `Link` whose doctype comes from a sibling field on the doc.
// `Color` is intentionally absent — it falls back to a text box until frappe-ui
// ships a color primitive to wrap (see plans/fieldtypes-remaining.md).
registerFieldType("Autocomplete", AutocompleteField);
registerFieldType("Rating", RatingField);
registerFieldType("Duration", DurationField);
registerFieldType("Dynamic Link", DynamicLinkField);

// Child table → inline-editable grid. Columns come from the schema
// (`field.childFields`, resolved by buildLayoutFromMeta); each cell reuses this
// same registry, so app field overrides apply inside the grid too.
registerFieldType("Table", TableField);

// `Read Only` renders as a disabled text box (buildLayoutFromMeta marks it
// `readOnly: true`, which TextField honours via `:disabled`).
registerFieldType("Read Only", TextField);

registerFieldType(FALLBACK, TextField);
