<!--
  The group's bracket as it passes one row, with the operator sitting on it. The
  cell is the default slot, so the bracket and the word it parts around are laid
  out together.

  Drawn as two lengths so it stops short of the word instead of running behind
  it. The lower one is a flex item after the cell rather than a span positioned a
  control's height down, so it starts wherever the cell actually ends and a
  two-line `#condition-conjunction` still works.
-->
<template>
	<div class="relative flex min-w-[66px] flex-col self-stretch">
		<span
			v-if="count > 1 && index > 0"
			aria-hidden="true"
			class="absolute start-1/2 border-s border-outline-gray-2"
			:style="above"
		/>
		<slot />
		<span
			v-if="count > 1 && index < count - 1"
			aria-hidden="true"
			class="w-0 flex-1 self-center border-s border-outline-gray-2"
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
	height: `${HALF_GAP + props.offset}px`,
}));

// Takes the rest of the column and reaches into the gap below.
const below = { marginBottom: `-${HALF_GAP}px` };
</script>
