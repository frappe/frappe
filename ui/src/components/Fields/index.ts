// Fields — the shared, fieldtype-aware value-input components plus the registry
// that dispatches a fieldtype to its control. Consumed by both `FormLayout`
// (form fields) and the ListView `Filter` / `Quick Filter` controls, so neither
// reaches across a module boundary for the other's value inputs (ADR-0004).
export { registerFieldType, getFieldComponent } from "./fieldTypes";
export type { RegisterFieldTypeOptions } from "./fieldTypes";

export { fieldtypeToLanguage } from "./fieldtypeToLanguage";

// The field contract every value-input satisfies, plus the form-context
// injection keys the deep-injection inputs (Table/Number/Image/DynamicLink) read.
export type {
  FieldMeta,
  FieldComponentProps,
  FieldComponentEmits,
} from "./types";
export { DocKey, ParentDocKey, UpdateKey } from "./types";
