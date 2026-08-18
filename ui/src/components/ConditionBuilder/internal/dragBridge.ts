import { computed } from "vue";
import type { ComputedRef } from "vue";
import { samePath } from "../tree";
import type { ConditionGroup, ConditionPath } from "../types";
import type { ConditionBuilderContext } from "./context";

interface DragEndEvent {
  from: HTMLElement;
  to: HTMLElement;
  oldIndex?: number;
  newIndex?: number;
}

/** A path as it is written on a row or a list. `""` is the root group. */
export function parsePath(value: string | null): ConditionPath | null {
  if (value === null) return null;
  if (value === "") return [];
  const path = value.split(".").map(Number);
  return path.every(Number.isInteger) ? path : null;
}

/**
 * Sortable's events, as tree edits. One group's half of a drag: whether it would
 * take the travelling row, and what to commit when the drop lands in it.
 */
export function useDragBridge(
  context: ConditionBuilderContext,
  path: ComputedRef<ConditionPath>,
  group: ComputedRef<ConditionGroup<unknown>>,
  nameOf: (node: unknown) => string
) {
  /**
   * One Sortable group per builder, so a row can be dragged anywhere in this
   * tree and nowhere in another.
   */
  const sortableGroup = computed(() => ({
    name: `condition-builder-${context.builderId.value}`,

    // Asked of the destination. Refusing during the drag means no indicator,
    // rather than landing and snapping back.
    put: (_to: unknown, _from: unknown, dragged: HTMLElement) => {
      const from = parsePath(dragged.getAttribute("data-condition-path"));
      return from !== null && context.canDrop(from, path.value);
    },
  }));

  /** Every group asks this of itself, so the fill marks every place the row
   *  can go. */
  const canTakeDrag = computed(() => {
    const from = context.dragFrom.value;
    return from !== null && context.canDrop(from, path.value);
  });

  /** Sortable tells only the list a drag starts in, which is where the row is. */
  function onDragStart(event: { oldIndex?: number }) {
    if (event.oldIndex === undefined) return;
    context.dragFrom.value = [...path.value, event.oldIndex];
  }

  /**
   * `end`, not `change`: a cross-group drop raises `change` twice, on two
   * components each holding the pre-drag tree. `end` fires once, on the source
   * list, with both lists and both indices.
   */
  function onDragEnd(event: DragEndEvent) {
    context.dragFrom.value = null;

    const from = parsePath(event.from.getAttribute("data-group-path"));
    const to = parsePath(event.to.getAttribute("data-group-path"));
    const { oldIndex, newIndex } = event;

    if (from === null || to === null) return;
    if (oldIndex === undefined || newIndex === undefined) return;
    if (samePath(from, to) && oldIndex === newIndex) return;

    // `end` fires on the source list, so this group holds the row that moved.
    const moved = samePath(from, path.value)
      ? group.value.conditions[oldIndex]
      : undefined;

    context.moveInto([...from, oldIndex], to, newIndex, {
      name: nameOf(moved),
    });
  }

  return { sortableGroup, canTakeDrag, onDragStart, onDragEnd };
}
