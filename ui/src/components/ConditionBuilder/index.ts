// ConditionBuilder, a controlled editor for a nested and/or condition tree.
// `adapters` holds everything that is not the component: reading and writing
// Frappe's interleaved condition array, and compiling the expression `safe_eval`
// runs. The operator and value-control rules are composed from `Filter`
// (ADR-0008), but every name a host imports is this component's own.
export { default as ConditionBuilder } from "./ConditionBuilder.vue";
export {
  emptyTree,
  fromFrappeConditions,
  isGroup,
  setGroupConjunction,
  toConditionExpression,
  toFrappeConditions,
} from "./adapters";
export type { ConditionExpressionOptions } from "./adapters";
export type {
  ConditionBorders,
  ConditionBuilderLabels,
  ConditionBuilderProps,
  ConditionColumns,
  ConditionField,
  ConditionGroup,
  ConditionNode,
  ConditionOperator,
  ConditionOperatorOption,
  ConditionPath,
  ConditionValue,
  Conjunction,
  FieldConditionValue,
} from "./types";
