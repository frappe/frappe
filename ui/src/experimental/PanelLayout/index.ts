// PanelLayout — a dense, one-column side-panel surface over the same layout
// resolver, fieldtype registry and formatters as `FormLayout`.
export { default as PanelLayout } from "./PanelLayout.vue";
export {
  displayValue,
  isSummaryField,
  isEmptyValue,
  summarize,
} from "./displayValue";
export type { PanelLayoutProps } from "./types";
