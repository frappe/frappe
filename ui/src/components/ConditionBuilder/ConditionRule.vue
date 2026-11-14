<!--
  The group's bracket as it passes one row, with the operator sitting on it. The
  cell is the default slot, so the bracket and the word it parts around are laid
  out together.

  Drawn as two lengths so it stops short of the word instead of running behind
  it. The lower one is a flex item after the cell rather than a span positioned a
  control's height down, so it starts wherever the cell actually ends and a
  two-line `#condition-conjunction` still works.

  The bracket runs at 28px, under the middle of both "Where" and the operator
  button, which start at the column's left edge. The bracket stops 4px short of a
  button's box, as it does of a word.
-->
<template>
	<div
		class="relative flex min-w-[66px] flex-col self-stretch [--stub-gap:0px] has-[button]:[--stub-gap:4px]"
	>
		<span
			v-if="count > 1 && index > 0"
			aria-hidden="true"
			class="absolute start-7 border-s border-outline-gray-3"
			:style="above"
		/>
		<slot />
		<span
			v-if="count > 1 && index < count - 1"
			aria-hidden="true"
			class="ms-7 w-0 flex-1 self-start border-s border-outline-gray-3"
			:style="below"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
	defineProps<{
		/** This row's index within its group. */
		index: number;

		/** How many rows the group holds. A group of one joins nothing. */
		count: number;

		/** How far below the row's top edge its first line starts. The row decides
		 *  it, because a card's first line sits inside the card's own chrome. */
		offset?: number;
	}>(),
	{ offset: 0 }
);

/** Half of the group's `gap-y-4`, which each end reaches into to meet the next. */
const HALF_GAP = 8;

// Bridges the row gap, then runs down to the word wherever the offset put it.
const above = computed(() => ({
	top: `-${HALF_GAP}px`,
	height: `calc(${HALF_GAP + props.offset}px - var(--stub-gap))`,
}));

// Takes the rest of the column and reaches into the gap below.
const below = { marginTop: "var(--stub-gap)", marginBottom: `-${HALF_GAP}px` };
</script>
