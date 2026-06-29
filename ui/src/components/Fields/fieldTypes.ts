import type { Component } from "vue";
import { setScoped } from "../../utils/scopedRegistry";
import AutocompleteField from "./AutocompleteField.vue";
import ButtonField from "./ButtonField.vue";
import CheckField from "./CheckField.vue";
import CodeEditorField from "./CodeEditorField.vue";
import DateField from "./DateField.vue";
import DatetimeField from "./DatetimeField.vue";
import DurationField from "./DurationField.vue";
import DynamicLinkField from "./DynamicLinkField.vue";
import AttachField from "./AttachField.vue";
import ImageField from "./ImageField.vue";
import GeolocationField from "./GeolocationField.vue";
import HeadingField from "./HeadingField.vue";
import HtmlField from "./HtmlField.vue";
import LinkField from "./LinkField.vue";
import NumberField from "./NumberField.vue";
import PasswordField from "./PasswordField.vue";
import PhoneField from "./PhoneField.vue";
import RatingField from "./RatingField.vue";
import SelectField from "./SelectField.vue";
import TableField from "./TableField.vue";
import TableMultiSelectField from "./TableMultiSelectField.vue";
import TextField from "./TextField.vue";
import TextareaField from "./TextareaField.vue";
import TimeField from "./TimeField.vue";

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

// Textarea for the plain multi-line text types.
for (const t of ["Small Text", "Text", "Long Text"]) {
  registerFieldType(t, TextareaField);
}

// Code-family types share one CodeEditorField (CodeMirror 6 writer + sanitized
// preview), with the language derived from the fieldtype/options.
for (const t of ["Code", "JSON", "Markdown Editor", "HTML Editor"]) {
  registerFieldType(t, CodeEditorField);
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

// `Attach` + `Attach Image` share one single-value field (value = `file_url`
// string); `imageOnly` is derived from the fieldtype inside AttachField. `Image`
// is display-only, mirroring the URL of the sibling field named in `options`.
// Multi-file lives in the AttachmentsList consumer, never as a fieldtype.
registerFieldType("Attach", AttachField);
registerFieldType("Attach Image", AttachField);
registerFieldType("Image", ImageField);

registerFieldType("Geolocation", GeolocationField);

// `Button` carries no value: its click rides the node's `ui.on.click` (schema- or
// decorate-supplied — see ButtonField). An undecorated Button is inert; apps can
// also register a richer override for the fieldtype.
registerFieldType("Button", ButtonField);

// Grid cells reuse this same registry, so app field overrides apply inside too.
registerFieldType("Table", TableField);

registerFieldType("Table MultiSelect", TableMultiSelectField);

// buildLayoutFromMeta marks `Read Only` as `readOnly`, which TextField disables.
registerFieldType("Read Only", TextField);

registerFieldType(FALLBACK, TextField);
