import type { Component } from "vue";
import type { InputLabelingProps } from "../types";
import type { FilterField, FilterOperator, FilterValue } from "../Filter/types";

export type Conjunction = "and" | "or";

/**
 * Derived from the rules it composes (ADR-0008), so the two cannot drift.
 * `timespan` is excluded: no expression compiles from one.
 */
export type ConditionOperator = Exclude<FilterOperator, "timespan">;
export type ConditionField = FilterField;

/** Widened by the two shapes the shared controls emit: a Rating number, and the
 *  null a date holds before anything is picked. */
export type ConditionValue = FilterValue | number | null;

export interface ConditionExpressionOptions {
  fieldPrefix?: string;
  fields?: ConditionField[];
}

export interface ConditionOperatorOption {
  label: string;
  value: ConditionOperator;
}

/** Child indices from the root group. `[]` addresses the root itself. */
export type ConditionPath = number[];

/** The built-in leaf. No resolved Meta on it, so a tree stays JSON. */
export interface FieldConditionValue {
  fieldname: string;
  operator: ConditionOperator;
  value: ConditionValue;
}

/**
 * One operator for the whole group, so a level reads `A and B and C`. Mixing is
 * expressed by nesting. The `conditions` array is what tells a group from a
 * leaf.
 */
export interface ConditionGroup<TLeaf = FieldConditionValue> {
  conjunction: Conjunction;
  conditions: ConditionNode<TLeaf>[];
}

export type ConditionNode<TLeaf = FieldConditionValue> =
  | TLeaf
  | ConditionGroup<TLeaf>;

/** Grid track sizes for the leaf's three cells. An `fr` stretches a cell past
 *  its content to use up the row's leftover width. */
export interface ConditionColumns {
  field?: string;
  operator?: string;
  value?: string;
}

/** `'all'` borders every group, `'root'` only the outer card, `'none'` neither. */
export type ConditionBorders = "all" | "root" | "none";

export interface ConditionBuilderLabels {
  where: string;
  and: string;
  or: string;

  /** Names the root `<fieldset>` and every nested `role="group"`. */
  matchAll: string;
  matchAny: string;

  /** Describes what the and/or button does. Never rendered as text. */
  conjunctionHint: string;

  addCondition: string;
  addGroup: string;
  turnIntoGroup: string;
  ungroup: string;
  remove: string;
  removeGroup: string;
  empty: string;

  /** Accessible names for the row and group menus. Never rendered as text. */
  rowActions: string;
  groupActions: string;

  /** Names for the three cells of the built-in leaf. Never rendered as text. */
  field: string;
  operator: string;
  value: string;

  fieldsError: string;
  retryFields: string;

  /** Functions, so the sentence is built in the host's language rather than
   *  assembled here from English fragments. */
  removed: (remaining: number, groupRemoved: boolean) => string;
  moved: (name: string, from: number, to: number, total: number) => string;
  movedToGroup: (name: string, to: number, total: number) => string;
}

/**
 * `label` / `description` / `error` / `required` are the shared labeling contract
 * every input control in this package exposes (frappe-ui P5). The tree is a value
 * the user enters, so the rule applies here as it does to Link and Phone.
 */
export interface ConditionBuilderProps<TLeaf = FieldConditionValue>
  extends InputLabelingProps {
  /** The tree, as `v-model`. `null` is an empty tree, which is what a nullable
   *  backend field bound straight to `v-model` arrives as. */
  modelValue: ConditionGroup<TLeaf> | null;

  /** The Python expression the tree compiles to. Write-only: never read back. */
  expression?: string;

  /** Prefixes every fieldname in the expression: `doc` for an SLA, nothing for
   *  an Assignment Rule. Affects nothing on screen. */
  fieldPrefix?: string;

  /** Doctype whose Meta drives the built-in leaf. Ignored when `fields` is
   *  supplied, unused when `#condition` replaces the leaf. */
  doctype?: string;

  fields?: ConditionField[];
  columns?: ConditionColumns;

  /** Root group is depth 0. Defaults to 4; past that a row has too little width. */
  maxDepth?: number;

  newCondition?: () => TLeaf;

  /** Read-only, not disabled: the rows keep their tab stops. */
  readonly?: boolean;

  /** For changing the wording. The defaults already go through the host's `__`. */
  labels?: Partial<ConditionBuilderLabels>;

  bordered?: ConditionBorders;

  /** Defaults to false. Turns off dragging between groups as well as within. */
  reorderable?: boolean;
}

export interface ConditionSlotProps<TLeaf = FieldConditionValue> {
  condition: TLeaf;
  path: ConditionPath;
  depth: number;
  readonly: boolean;
  update: (leaf: TLeaf) => void;
}

export interface ValueSlotProps {
  field: ConditionField | undefined;
  operator: ConditionOperator;
  modelValue: ConditionValue;

  /** True for a read-only builder, an unknown field, or a fieldtype with no
   *  value control. The slot renders in all of them and must not call `update`. */
  readonly: boolean;
  update: (value: ConditionValue) => void;
}

/** Props for `#group`, which wraps a **nested** group. The root is the builder
 *  itself, so a host wraps it where it mounts it rather than through a slot. */
export interface GroupSlotProps<TLeaf = FieldConditionValue> {
  group: ConditionGroup<TLeaf>;

  /** Child indices from the root. Never `[]`. */
  path: ConditionPath;
  depth: number;
  readonly: boolean;

  /** The default rendering. `<component :is="Group" />` puts the real recursive
   *  group wherever the host renders it, a teleported dialog included. Takes no
   *  props: the node is read from the tree on each render. */
  Group: Component;
}

export interface WhereSlotProps {
  groupPath: ConditionPath;
  conjunction: Conjunction;
}

export interface ConjunctionSlotProps {
  conjunction: Conjunction;

  /** This row's index within its group. Always 1 or greater. */
  index: number;
  groupPath: ConditionPath;
  toggle: () => void;

  /** Exactly one cell in a group is live: row 1. A cell that is not should
   *  render the word as text, not as a disabled button. */
  canToggle: boolean;
}

export interface ActionsSlotProps {
  path: ConditionPath;
  isGroup: boolean;
  readonly: boolean;

  /** Whether `turnIntoGroup` would do anything: false for a group, and false
   *  where nesting here would exceed `maxDepth`. */
  canGroup: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  moveUp: () => void;
  moveDown: () => void;
  turnIntoGroup: () => void;
  ungroup: () => void;
  remove: () => void;
}

export interface AddConditionSlotProps {
  groupPath: ConditionPath;
  addCondition: () => void;
  addGroup: () => void;
  canAddGroup: boolean;
}

export interface ConditionBuilderSlots<TLeaf = FieldConditionValue> {
  /** Replaces the entire leaf row. */
  condition?: (props: ConditionSlotProps<TLeaf>) => unknown;

  /**
   * Wraps or replaces a nested group. An empty template renders the default;
   * `<span />` renders no group at all, leaving its rows unreachable.
   */
  group?: (props: GroupSlotProps<TLeaf>) => unknown;

  /** Replaces only the value control inside the built-in leaf. */
  "condition-value"?: (props: ValueSlotProps) => unknown;

  /** Replaces the empty-state content. */
  empty?: () => unknown;

  /** Render a `<span />` to draw nothing. */
  "condition-where"?: (props: WhereSlotProps) => unknown;
  "condition-conjunction"?: (props: ConjunctionSlotProps) => unknown;
  "condition-actions"?: (props: ActionsSlotProps) => unknown;
  "add-condition"?: (props: AddConditionSlotProps) => unknown;
}
