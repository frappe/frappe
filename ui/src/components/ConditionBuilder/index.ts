// ConditionBuilder, a controlled editor for a nested and/or condition tree.
// `adapters` holds everything that is not the component: reading and writing
// Frappe's interleaved condition array, and compiling the expression `safe_eval`
// runs. `dependsOn` reads and writes a DocField's `depends_on` condition, and
// `ConditionValueControl` is the built-in value cell, for a host's own
// `#condition-value`. The operator and value-control rules are composed from
// `Filter`, but every name a host imports is this component's own.
export { default as ConditionBuilder } from "./ConditionBuilder.vue";
export { default as ConditionValueControl } from "./ConditionValueControl.vue";
export {
  emptyTree,
  fromFrappeConditions,
  isGroup,
  setGroupConjunction,
  toConditionExpression,
  toFrappeConditions,
} from "./adapters";
export type { ConditionExpressionOptions } from "./adapters";
export {
  dependsOnScope,
  fieldReference,
  fromDependsOn,
  referencedField,
  toDependsOn,
} from "./dependsOn";
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
  DependsOnScope,
  FieldConditionValue,
} from "./types";
