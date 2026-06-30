export { default as FormLayout } from "./FormLayout.vue";
export { useFieldTypes } from "./useFieldTypes";
export { registerFieldType, getFieldComponent } from "../Fields/fieldTypes";
export type { RegisterFieldTypeOptions } from "../Fields/fieldTypes";

// The file-upload primitive now lives in its own module — import upload
// consumers, the headless engine, and the source seam from "@framework/ui/FileUpload".
export { useDoctypeLayout } from "./useDoctypeLayout";
export { useScriptedLayout } from "./useScriptedLayout";
export { useChildRowModel } from "./useChildRowModel";
export { buildLayoutFromMeta, compose } from "./buildLayoutFromMeta";
export type { BuildLayoutOptions, Decorator } from "./buildLayoutFromMeta";
export { fieldsToLayout } from "./fieldsToLayout";
export { resolveLayout } from "./resolveLayout";
export { applyMetaScript } from "./applyMetaScript";
export type { MetaOp } from "./applyMetaScript";
export { evaluateDependsOn } from "./dependsOn";
export {
  flt,
  formatNumber,
  formatCurrency,
  formatField,
  getCurrencySymbol,
  getNumberFormatInfo,
  DEFAULT_NUMBER_FORMAT,
  DEFAULT_ROUNDING_METHOD,
} from "./formatNumber";
export {
  getFormatDefaults,
  setFormatDefaults,
  resetFormatDefaults,
} from "./formatDefaults";
export type {
  FormLayoutSchema,
  Tab,
  Section,
  Column,
  FieldMeta,
  FieldNode,
  FieldUI,
  RawMetaField,
  FieldComponentProps,
  FieldComponentEmits,
} from "./types";
export type { UseDoctypeLayout } from "./useDoctypeLayout";
export type {
  FltOptions,
  FormatNumberOptions,
  FormatCurrencyOptions,
  FormatFieldOptions,
  NumberFormatInfo,
} from "./formatNumber";
export type { FormatDefaults } from "./formatDefaults";
