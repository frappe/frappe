<!-- The apps' standing windows: one row on the shell's bottom line, left of a floating composer and the Flow launcher or panel. -->
<template>
	<div
		ref="rowEl"
		class="pointer-events-none fixed z-40 flex w-max items-end gap-3"
		:style="{ right: `${right}px`, bottom: `${bottom}px`, maxWidth: `${room}px` }"
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
import { computed, nextTick, ref, watch } from "vue";
import { useElementBounding, useResizeObserver, useWindowSize } from "@vueuse/core";
import { composerBand, floatingComposer } from "./composer";
import { useFlowLauncher } from "./flowLauncher";
import type { Shell } from "./shellActs";
import StandingWindowFrame from "./StandingWindowFrame.vue";
import type { StandingWindow } from "./standingWindows";
import { useTabKeepAlive } from "./tabKeepAlive";
import { navInsetRight } from "./navigationInset";
import { MARGIN } from "./windowDrag";

const props = defineProps<{ windows: readonly StandingWindow[]; shell: Shell }>();
useTabKeepAlive(() => props.windows);

const GAP = 12;

const viewport = useWindowSize();
// The most the row may take; a wider row would leave the screen at its right end.
const room = computed(() => viewport.width.value - 2 * MARGIN - navInsetRight.value);
const band = useElementBounding(composerBand);
// The lane is centred in its band, so it moves sideways with no resize of its own.
useResizeObserver(
	() => composerBand()?.parentElement ?? null,
	() => band.update()
);
// Also follows the card's `style`, which is all a drag changes.
const card = useElementBounding(floatingComposer);

const rowEl = ref<HTMLElement | null>(null);
const row = useElementBounding(rowEl);

const { box: launcher, dockedLeft } = useFlowLauncher();

const besideComposer = computed(() =>
	floatingComposer() ? viewport.width.value - card.left.value + GAP : MARGIN + navInsetRight.value
);
// A launcher dragged into the row's way, or within a gap of its end, sits at the row's right end like a composer.
const besideLauncher = computed(() => {
	const box = launcher.value;
	const rowRight = viewport.width.value - besideComposer.value;
	const lineBottom = viewport.height.value - MARGIN;
	const onLine = box && box.top < lineBottom && box.bottom > lineBottom - row.height.value;
	const inWay = box && box.right > rowRight - row.width.value && box.left < rowRight + GAP;
	return onLine && inWay ? viewport.width.value - box.left + GAP : 0;
});

// The Flow panel docked on the right covers the whole edge, so the row sits left of it at any height.
const besideDock = computed(() =>
	dockedLeft.value === null ? 0 : viewport.width.value - dockedLeft.value + GAP
);

// A composer dragged far left may be overlapped: the row never leaves the screen.
const right = computed(() => {
	const beside = Math.max(besideComposer.value, besideLauncher.value, besideDock.value);
	return Math.min(beside, viewport.width.value - MARGIN - row.width.value);
});
const overlapsBand = computed(() => {
	const rowRight = viewport.width.value - right.value;
	return rowRight - row.width.value < band.right.value && rowRight > band.left.value;
});
const bottom = computed(() =>
	composerBand() && overlapsBand.value ? viewport.height.value - band.top.value + GAP : MARGIN
);
// A row too wide for the room minimises its open windows from the left, sparing the one just
// opened (else the rightmost), and a pill that still does not fit truncates its title.
let wasOpen = new Set<string>();
let fitting = false;
let refit = false;
async function fit() {
	if (fitting) {
		refit = true;
		return;
	}
	fitting = true;
	try {
		do {
			refit = false;
			// v-show applies in the same flush's post queue, after this watcher.
			await nextTick();
			await minimiseUntilFit();
			wasOpen = new Set(openWindows().map((entry) => entry.app));
		} while (refit);
	} finally {
		fitting = false;
	}
}

async function minimiseUntilFit() {
	while (rowEl.value && rowEl.value.getBoundingClientRect().width >= room.value) {
		const open = openWindows();
		const spared = [...open].reverse().find((entry) => !wasOpen.has(entry.app)) ?? open.at(-1);
		const next = open.find((entry) => entry !== spared);
		if (!next) return;
		next.handle.minimise();
		await nextTick();
	}
}

const openWindows = () => props.windows.filter((entry) => entry.state === "open" && !entry.placed);
watch(() => [props.windows.map((entry) => entry.state).join(), room.value, row.width.value], fit, {
	flush: "post",
});

const maxHeight = computed(() => viewport.height.value - bottom.value - MARGIN);
</script>
