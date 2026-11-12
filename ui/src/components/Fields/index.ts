// Fields — the shared, fieldtype-aware value-input components plus the registry
// that dispatches a fieldtype to its control. Consumed by both `FormLayout`
// (form fields) and the ListView `Filter` / `Quick Filter` controls, so neither
// reaches across a module boundary for the other's value inputs.
export { registerFieldType, getFieldComponent } from "./fieldTypes";
export type { RegisterFieldTypeOptions } from "./fieldTypes";

export { fieldtypeToLanguage } from "./fieldtypeToLanguage";
export { fileName } from "./fileName";
export { focusField } from "./focusField";
export { copyRow, holdsChildRows, identify, ROW_ID, rowKey } from "./rowIdentity";
export { useRecordLink } from "./useRecordLink";
export { drawsReadValue } from "./readView";
export { default as ReadOnlyField } from "./ReadOnlyField.vue";
export { default as ReadValue } from "./ReadValue.vue";
export { default as FieldBox } from "./FieldBox.vue";
export { default as SelectedChip } from "../TableMultiSelect/SelectedChip.vue";
export { LINE_HEIGHT, MAX_HEIGHT, MAX_LINES, PADDING, useTextareaGrow } from "./useTextareaGrow";
export { default as FieldDescription } from "./FieldDescription.vue";
export { descriptionText } from "./fieldDescription";
export { dataHref, groupIban, isEmailField, isPhoneField } from "./dataOptions";
export type { DataHref } from "./dataOptions";
export { default as DataOpenLink } from "./DataOpenLink.vue";
export { default as FieldActionButtons } from "./FieldActions.vue";
export { default as ColorSwatch } from "./ColorSwatch.vue";
export { default as LinkMark } from "./LinkMark.vue";
export { useLinkMark } from "./useLinkMark";

// The field contract every value-input satisfies, plus the form-context
// injection keys the deep-injection inputs (Table/Number/Image/DynamicLink) read.
export type {
  FieldAction,
  FieldActions,
  FieldRecord,
  FieldMeta,
  FieldComponentProps,
  FieldComponentEmits,
  FieldAddress,
  FieldError,
  LinkMarkSource,
} from "./types";
export {
  DocKey,
  FieldActionsKey,
  FieldErrorsKey,
  LinkMarksKey,
  LinkTitlesKey,
  ParentDocKey,
  TemplateNamesKey,
  UpdateKey,
  fieldErrorKey,
  markedFieldnames,
} from "./types";
