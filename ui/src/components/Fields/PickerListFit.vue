<!-- Rendered in a picker's footer slot, so it mounts inside the portaled list: frappe-ui gives a list no class
     or width prop. It caps the list at its bound, and titles an option the list truncates. -->
<template>
	<span ref="marker" class="hidden" aria-hidden="true" />
</template>

<script setup lang="ts">
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import { fieldBoxKey } from "./fieldBox";

// Select keeps this far from the viewport edge when it shifts a wide list left.
const EDGE_GAP = 10;

const marker = ref<HTMLElement | null>(null);
const box = inject(fieldBoxKey, ref(null));
let list: HTMLElement | null = null;

function titleTruncated(event: MouseEvent) {
	const option = (event.target as Element).closest<HTMLElement>('[role="option"]');
	if (!option) return;
	const cut = [...option.querySelectorAll<HTMLElement>(".truncate")].some(
		(label) => label.scrollWidth > label.clientWidth
	);
	option.title = cut ? option.textContent!.trim().replace(/\s+/g, " ") : "";
}

onMounted(() => {
	list = marker.value?.closest<HTMLElement>('[data-slot="content"]') ?? null;
	const bound = box.value?.closest<HTMLElement>("[data-picker-bound]")?.getBoundingClientRect();
	if (bound?.width) {
		// The viewport edge shifts a wide list left, so the cap also keeps its left edge on the bound's.
		const room = Math.min(bound.width, innerWidth - bound.left - EDGE_GAP);
		list?.style.setProperty("max-width", `${room}px`);
	}
	list?.addEventListener("mouseover", titleTruncated);
});

onBeforeUnmount(() => list?.removeEventListener("mouseover", titleTruncated));
</script>
