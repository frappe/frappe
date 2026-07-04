// ColumnSettings — the controlled, meta-driven list-view column control plus its
// pure, frappe-ui-free helpers. The control's `v-model` is an ordered `Column[]`
// (presence = shown, order = display order, `width` = the slice a resize
// co-writes). `serializeColumns` maps it to frappe-ui's `ListView` render shape
// (deriving `align`/`type`/`options` from Meta) and `parseColumns` recovers it;
// Field Options come from Meta with `getColumnOptions`.
export { default as ColumnSettings } from "./ColumnSettings.vue";
export {
  serializeColumns,
  parseColumns,
  getColumnAlign,
  applyColumnWidth,
  clearColumnWidth,
  dropOrphanedSyntheticColumns,
  fetchFields,
  SYNTHETIC_KEY_PREFIX,
} from "./columns";
export { getColumnOptions } from "./getColumnOptions";
export { getDefaultColumns, foldSyntheticColumns } from "./getDefaultColumns";
export type {
  Column,
  ColumnOption,
  SyntheticColumn,
  WireColumn,
} from "./types";
