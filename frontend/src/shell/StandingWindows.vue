<!-- The apps' standing windows: one row on the shell's bottom line, left of a floating composer. -->
<template>
	<div
		ref="rowEl"
		class="pointer-events-none fixed z-40 flex items-end gap-3"
		:style="{ right: `${right}px`, bottom: `${bottom}px` }"
		data-standing-row
	>
		<StandingWindowFrame
			v-for="entry in windows"
			:key="entry.app"
			:entry="entry"
			:shell="shell"
			:max-height="maxHeight"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useElementBounding, useWindowSize } from "@vueuse/core";
import { composerBand, floatingComposer } from "./composer";
import type { Shell } from "./shellActs";
import StandingWindowFrame from "./StandingWindowFrame.vue";
import type { StandingWindow } from "./standingWindows";

defineProps<{ windows: readonly StandingWindow[]; shell: Shell }>();

const MARGIN = 24;
const GAP = 12;

const viewport = useWindowSize();
const band = useElementBounding(composerBand);
// Also follows the card's `style`, which is all a drag changes.
const card = useElementBounding(floatingComposer);

const rowEl = ref<HTMLElement | null>(null);
const row = useElementBounding(rowEl);

// A composer dragged far left may be overlapped: the row never leaves the screen.
const right = computed(() => {
	const beside = floatingComposer() ? viewport.width.value - card.left.value + GAP : MARGIN;
	return Math.min(beside, viewport.width.value - MARGIN - row.width.value);
});
const overlapsBand = computed(() => {
	const rowRight = viewport.width.value - right.value;
	return rowRight - row.width.value < band.right.value && rowRight > band.left.value;
});
const bottom = computed(() =>
	composerBand() && overlapsBand.value ? viewport.height.value - band.top.value + GAP : MARGIN
);
const maxHeight = computed(() => viewport.height.value - bottom.value - MARGIN);
</script>
