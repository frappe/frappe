import { customRef, inject } from "vue";
import type { ComputedRef, InjectionKey, Ref } from "vue";
import type {
  ConditionBorders,
  ConditionBuilderLabels,
  ConditionColumns,
  ConditionField,
  ConditionPath,
  Conjunction,
} from "../types";

/**
 * Shared by every node. Mutations are reported by path, so no group relays
 * events up through its own recursion.
 */
export interface ConditionBuilderContext {
  /** Scopes the focus queries: a path is only unique inside one builder. */
  builderId: ComputedRef<string>;

  /** Ids of the host-facing label, description and error, for the root group to
   *  name and describe itself with. Empty string where there is none. */
  labelId: ComputedRef<string>;
  describedBy: ComputedRef<string>;
  invalid: ComputedRef<boolean>;

  fields: ComputedRef<ConditionField[]>;

  /** While Meta is in flight a missing fieldname means "not loaded" rather than
   *  "not a field any more", and the two get opposite treatments in the leaf. */
  fieldsLoading: ComputedRef<boolean>;
  fieldsError: ComputedRef<unknown>;
  reloadFields: () => void;

  columns: ComputedRef<Required<ConditionColumns>>;
  labels: Ref<ConditionBuilderLabels>;
  bordered: ComputedRef<ConditionBorders>;
  maxDepth: ComputedRef<number>;
  readonly: ComputedRef<boolean>;
  reorderable: ComputedRef<boolean>;

  addCondition: (groupPath: ConditionPath) => void;
  addGroup: (groupPath: ConditionPath) => void;
  remove: (path: ConditionPath) => void;
  update: (path: ConditionPath, leaf: unknown) => void;
  turnIntoGroup: (path: ConditionPath) => void;
  ungroup: (path: ConditionPath) => void;
  setConjunction: (groupPath: ConditionPath, value: Conjunction) => void;

  /** Reorder one child within its group. Only a menu move places focus; a
   *  pointer drop has not taken any. */
  move: (
    groupPath: ConditionPath,
    from: number,
    to: number,
    options?: { name?: string; focus?: boolean }
  ) => void;

  /** Asked while a drag is in flight, so a drop past `maxDepth` shows no
   *  indicator rather than landing and snapping back. */
  canDrop: (from: ConditionPath, toGroupPath: ConditionPath) => boolean;

  /** The row being dragged. Shared, because a row can land in any group and each
   *  one answers for itself whether it would take it. */
  dragFrom: Ref<ConditionPath | null>;

  /** The pointer's edit: a drop into any group, run once, from the list the drag
   *  started in. It takes no focus and places none. */
  moveInto: (
    from: ConditionPath,
    toGroupPath: ConditionPath,
    toIndex: number,
    options?: { name?: string }
  ) => void;

  /** Put a message in the builder's live region. */
  announce: (message: string) => void;
}

export const conditionBuilderKey: InjectionKey<ConditionBuilderContext> =
  Symbol("conditionBuilder");

/**
 * Resolved per row, so only a row naming a long field pays for it. No `fr`: it
 * is a share of the leftover and would stretch a cell past its content.
 * `minmax(0, ...)` because a bare `max-content` floors at min-content and
 * overflows a narrow container.
 */
export const DEFAULT_COLUMNS: Required<ConditionColumns> = {
  field: "minmax(0, max-content)",
  operator: "minmax(0, max-content)",
  value: "minmax(0, max-content)",
};

/** Deepest nesting level offered. The root group is depth 0. */
export const DEFAULT_MAX_DEPTH = 4;

export const DEFAULT_BORDERS: ConditionBorders = "all";

/** Off, so a flat filter does not have to opt out. */
export const DEFAULT_REORDERABLE = false;

/**
 * Read off the global at call time: this package has no i18n of its own. Values
 * go through `{0}`, since a sentence glued from translated halves only reads in
 * English.
 */
function t(message: string, replace?: unknown[]): string {
  const translate = (
    globalThis as { __?: (m: string, r?: unknown[]) => string }
  ).__;
  if (typeof translate === "function") return translate(message, replace);
  if (!replace) return message;
  // The fallback substitutes too, or a literal `{0}` is read out on a host with
  // no plugin.
  return message.replace(/\{(\d+)\}/g, (match, index) => {
    const value = replace[Number(index)];
    return value === undefined ? match : String(value);
  });
}

/**
 * A function, not a const: a module-level object is built before the host
 * installs its translations, freezing every label as English.
 */
export function defaultLabels(): ConditionBuilderLabels {
  return {
    where: t("Where"),
    and: t("and"),
    or: t("or"),
    matchAll: t("Match all of the following"),
    matchAny: t("Match any of the following"),
    conjunctionHint: t("Changes how every condition in this group is joined"),
    addCondition: t("Add Condition"),
    addGroup: t("Add Condition Group"),
    turnIntoGroup: t("Turn into a Group"),
    ungroup: t("Ungroup Conditions"),
    remove: t("Remove"),
    removeGroup: t("Remove Group"),
    empty: t("Add a Condition"),
    rowActions: t("Condition actions"),
    groupActions: t("Group actions"),
    field: t("Field"),
    operator: t("Operator"),
    value: t("Value"),
    fieldsError: t("Could not load this doctype's fields."),
    retryFields: t("Retry"),
    removed: (remaining, groupRemoved) =>
      [
        t("Condition removed."),
        groupRemoved ? t("Its group was left empty and was removed too.") : "",
        t("{0} remaining.", [remaining]),
      ]
        .filter(Boolean)
        .join(" "),
    movedToGroup: (name, to, total) =>
      name
        ? t("{0} moved into another group, at position {1} of {2}.", [
            name,
            to,
            total,
          ])
        : t("Condition moved into another group, at position {0} of {1}.", [
            to,
            total,
          ]),
    moved: (name, from, to, total) =>
      name
        ? t("{0} moved from position {1} to position {2} of {3}.", [
            name,
            from,
            to,
            total,
          ])
        : t("Condition moved from position {0} to position {1} of {2}.", [
            from,
            to,
            total,
          ]),
  };
}

/**
 * Re-read on every access, so the host's messages land. A `computed` caches the
 * first read; a bare getter object is not a ref.
 */
export function uncachedLabels(
  read: () => ConditionBuilderLabels
): Ref<ConditionBuilderLabels> {
  let probe = t("Where");
  return customRef((track, trigger) => ({
    get() {
      track();
      const current = t("Where");
      if (current !== probe) {
        probe = current;
        queueMicrotask(trigger);
      }
      return read();
    },
    set() {},
  }));
}

/**
 * Not a spread: an object built from optional values carries explicit
 * `undefined` keys, which a spread copies over the defaults.
 */
function overlay<T extends object>(defaults: T, overrides?: Partial<T>): T {
  const merged = { ...defaults };
  if (!overrides) return merged;
  for (const [key, value] of Object.entries(overrides)) {
    if (value === undefined || !(key in defaults)) continue;
    (merged as Record<string, unknown>)[key] = value;
  }
  return merged;
}

export function mergeLabels(
  overrides?: Partial<ConditionBuilderLabels>
): ConditionBuilderLabels {
  return overlay(defaultLabels(), overrides);
}

export function mergeColumns(
  overrides?: ConditionColumns
): Required<ConditionColumns> {
  return overlay(DEFAULT_COLUMNS, overrides);
}

export function useConditionBuilderContext(): ConditionBuilderContext {
  const context = inject(conditionBuilderKey, null);
  if (!context) {
    throw new Error(
      "ConditionBuilder: this component must be used inside one."
    );
  }
  return context;
}
