import { computed } from "vue";
import type { ComputedRef } from "vue";
import { isGroup } from "../tree";
import type { ConditionBorders, ConditionColumns } from "../types";

/** The leading conjunction cell, wide enough for `Where` at any of its lengths. */
const CONJUNCTION_TRACK = "minmax(66px, max-content)";

/**
 * Takes the row's leftover width, so the actions land on the end edge in every
 * row. `max-content` floors it so the buttons are never squeezed.
 */
const ACTIONS_TRACK = "minmax(max-content, 1fr)";

/**
 * The card's border and `p-3`, both set on the group element so they move
 * together.
 */
const CARD_FIRST_LINE = 13;

/**
 * A group's grid arithmetic: which tracks a row has, and how far into it the
 * first line starts. No markup, so it is here rather than in the component.
 */
export function useConditionLayout(
  columns: ComputedRef<Required<ConditionColumns>>,
  bordered: ComputedRef<ConditionBorders>,
  canReorder: ComputedRef<boolean>
) {
  // Only where there is a handle: an empty track would indent every row of a
  // fixed tree.
  const handleTrack = computed(() => (canReorder.value ? ["max-content"] : []));

  const trackList = computed(() =>
    [
      CONJUNCTION_TRACK,
      ...handleTrack.value,
      columns.value.field,
      columns.value.operator,
      columns.value.value,
      ACTIONS_TRACK,
    ].join(" ")
  );

  // A card's row is one stretching track: a group has no field, operator or
  // value of its own.
  const groupTrackList = computed(() =>
    [
      CONJUNCTION_TRACK,
      ...handleTrack.value,
      "minmax(0, 1fr)",
      "max-content",
    ].join(" ")
  );

  function trackListFor(node: unknown): string {
    return isGroup(node) ? groupTrackList.value : trackList.value;
  }

  /**
   * Zero for a leaf. A card's first rule begins inside its border and padding,
   * and the operator joining it belongs beside that rule.
   */
  function firstLineOffset(node: unknown): number {
    const drawsCard = isGroup(node) && bordered.value === "all";
    return drawsCard ? CARD_FIRST_LINE : 0;
  }

  /** The offset as the row's cells take it; the bracket takes the number. */
  function firstLineStyle(node: unknown): { marginTop: string } | undefined {
    const offset = firstLineOffset(node);
    return offset ? { marginTop: `${offset}px` } : undefined;
  }

  return { trackListFor, firstLineOffset, firstLineStyle };
}
