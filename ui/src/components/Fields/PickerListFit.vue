<!-- Rendered in a picker's footer slot, so it mounts inside the portaled list: frappe-ui gives a list no class
     or size prop. It caps the list at its bound and at the room below the row, and titles an option the list truncates. -->
<template>
	<span ref="marker" class="hidden" aria-hidden="true" />
</template>

<script setup lang="ts">
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import { fieldBoxKey } from "./fieldBox";

// Select keeps this far from the viewport edge when it shifts a wide list left.
const EDGE_GAP = 10;
// The list sits 4px under the row (frappe-ui's offset); the popper flips a list that comes within 10px of
// the window's bottom, so a list capped to this gap stays below.
const BELOW_GAP = 16;
// A list needs about this much room under its row to be usable; a row nearer the window's bottom scrolls up.
const MIN_LIST = 120;

const marker = ref<HTMLElement | null>(null);
const box = inject(fieldBoxKey, ref(null));
let list: HTMLElement | null = null;
let scroller: HTMLElement | null = null;
let ownMaxHeight: string | null = null;

function titleTruncated(event: MouseEvent) {
	const option = (event.target as Element).closest<HTMLElement>('[role="option"]');
	if (!option) return;
	const cut = [...option.querySelectorAll<HTMLElement>(".truncate")].some(
		(label) => label.scrollWidth > label.clientWidth
	);
	option.title = cut ? option.textContent!.trim().replace(/\s+/g, " ") : "";
}

function scrollParents(node: HTMLElement | null) {
	const parents: HTMLElement[] = [];
	for (; node; node = node.parentElement)
		if (
			/auto|scroll/.test(getComputedStyle(node).overflowY) &&
			node.scrollHeight > node.clientHeight
		)
			parents.push(node);
	return parents;
}

// A row with less than MIN_LIST under it scrolls up inside its scrollers, the nearest first, so the list
// has room to open below.
function makeRoom() {
	const row = box.value?.getBoundingClientRect();
	if (!row) return;
	let short = MIN_LIST + BELOW_GAP - (innerHeight - row.bottom);
	for (const parent of scrollParents(box.value)) {
		if (short <= 0) break;
		const before = parent.scrollTop;
		parent.scrollBy({ top: short, behavior: "instant" });
		short -= parent.scrollTop - before;
	}
}

// The list always opens below its row. Capping it to the room under the row keeps the popper from
// flipping it above; a list taller than that scrolls.
function fitBelow() {
	const row = box.value?.getBoundingClientRect();
	const scroller = findScroller();
	if (!row || !scroller) return;
	if (ownMaxHeight === null) ownMaxHeight = getComputedStyle(scroller).maxHeight;
	const room = `${Math.max(innerHeight - row.bottom - BELOW_GAP, 0)}px`;
	scroller.style.maxHeight =
		!ownMaxHeight || ownMaxHeight === "none" ? room : `min(${ownMaxHeight}, ${room})`;
}

// Chrome makes a list that overflows a Tab stop. A Tab from the last row would land in it, not leave the row.
function leaveTabOrder() {
	findScroller()?.setAttribute("tabindex", "-1");
}

function findScroller() {
	scroller ??= list?.querySelector<HTMLElement>('[role="presentation"]') ?? null;
	return scroller;
}

onMounted(() => {
	list = marker.value?.closest<HTMLElement>('[data-slot="content"]') ?? null;
	makeRoom();
	fitBelow();
	leaveTabOrder();
	addEventListener("resize", fitBelow);
	addEventListener("scroll", fitBelow, true);
	const bound = box.value?.closest<HTMLElement>("[data-picker-bound]")?.getBoundingClientRect();
	if (bound?.width) {
		// The viewport edge shifts a wide list left, so the cap also keeps its left edge on the bound's.
		const room = Math.min(bound.width, innerWidth - bound.left - EDGE_GAP);
		list?.style.setProperty("max-width", `${room}px`);
	}
	list?.addEventListener("mouseover", titleTruncated);
});

onBeforeUnmount(() => {
	list?.removeEventListener("mouseover", titleTruncated);
	removeEventListener("resize", fitBelow);
	removeEventListener("scroll", fitBelow, true);
});
</script>
