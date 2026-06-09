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
import TableMultiSelectField from "./fields/TableMultiSelectField.vue";
import TextField from "./fields/TextField.vue";
import TextareaField from "./fields/TextareaField.vue";
import TimeField from "./fields/TimeField.vue";

/** Process-global fieldtype → component registry. */
const registry = new Map<string, Component>();

const FALLBACK = "__fallback__";

export interface RegisterFieldTypeOptions {
  /**
   * `true` (default): register globally for the process.
   * `false`: register scoped to the current Vue effect scope; the previous
   * mapping auto-restores on scope dispose (component unmount). Must be called
   * synchronously in `setup`; falls back to global + warns if no active scope.
   */
  global?: boolean;
}

export function registerFieldType(
  fieldtype: string,
  component: Component,
  options: RegisterFieldTypeOptions = {}
): void {
  const { global = true } = options;

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

// One numeric control formats per fieldtype with lib defaults; apps register
// their own for site-accurate settings (see formatNumber.ts).
for (const t of ["Int", "Float", "Currency", "Percent"]) {
  registerFieldType(t, NumberField);
}

// Textarea for all multi-line text types; code/editor types ride along until a
// shared CodeEditorField exists (no frappe-ui code-editor primitive yet).
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

// `Heading`/`HTML` are display-only (no value, no emit).
registerFieldType("Phone", PhoneField);
registerFieldType("Heading", HeadingField);
registerFieldType("HTML", HtmlField);

registerFieldType("Password", PasswordField);

// `Color` is intentionally absent — falls back to a text box until frappe-ui
// ships a color primitive (see plans/fieldtypes-remaining.md).
registerFieldType("Autocomplete", AutocompleteField);
registerFieldType("Rating", RatingField);
registerFieldType("Duration", DurationField);
registerFieldType("Dynamic Link", DynamicLinkField);

// Grid cells reuse this same registry, so app field overrides apply inside too.
registerFieldType("Table", TableField);

registerFieldType("Table MultiSelect", TableMultiSelectField);

// buildLayoutFromMeta marks `Read Only` as `readOnly`, which TextField disables.
registerFieldType("Read Only", TextField);

registerFieldType(FALLBACK, TextField);
