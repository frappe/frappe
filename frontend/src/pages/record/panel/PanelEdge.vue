<!-- The seam between the main column and the panel: drag to resize, drag past the minimum
     to collapse, click for the same toggle the round chevron gives. -->
<template>
	<div class="group/edge relative z-20 w-0 shrink-0">
		<div
			class="absolute inset-y-0 -left-2 w-4 cursor-w-resize"
			@click="onClick"
			@pointerdown.prevent="onPointerDown"
		/>

		<button
			type="button"
			class="absolute -left-3 bottom-1/3 grid size-6 translate-y-1/2 place-content-center rounded-full border border-outline-gray-2 bg-surface-base text-ink-gray-5 shadow-sm transition hover:bg-surface-gray-2 focus-visible:opacity-100 group-hover/edge:opacity-100"
			:class="open ? 'opacity-0' : 'opacity-100'"
			:aria-label="open ? 'Hide details panel' : 'Show details panel'"
			:aria-expanded="open"
			@click="emit('toggle')"
		>
			<span
				class="size-4"
				:class="open ? 'lucide-chevron-right' : 'lucide-chevron-left'"
				aria-hidden="true"
			/>
		</button>
	</div>
</template>

<script setup lang="ts">
import { onBeforeUnmount } from "vue";
import { dragOutcome } from "./geometry";

const props = defineProps<{ open: boolean; width: number }>();
const emit = defineEmits<{ toggle: []; "update:width": [number] }>();

// The panel animates its width open and shut, and must not animate under a drag.
const dragging = defineModel<boolean>("dragging", { default: false });

let startX = 0;
let startWidth = 0;
let dragged = false;

function onPointerDown(event: PointerEvent) {
	startX = event.clientX;
	startWidth = props.width;
	dragged = false;
	dragging.value = true;
	window.addEventListener("pointermove", onPointerMove);
	window.addEventListener("pointerup", stopDrag, { once: true });
	window.addEventListener("pointercancel", stopDrag, { once: true });
}

onBeforeUnmount(stopDrag);

function onPointerMove(event: PointerEvent) {
	const distance = startX - event.clientX;
	if (props.open && Math.abs(distance) > 2) dragged = true;

	const { width, toggle } = dragOutcome(props.open, startWidth, distance);
	if (width) emit("update:width", width);
	if (!toggle) return;
	dragged = true;
	emit("toggle");
	stopDrag();
}

function stopDrag() {
	dragging.value = false;
	window.removeEventListener("pointermove", onPointerMove);
	window.removeEventListener("pointerup", stopDrag);
	window.removeEventListener("pointercancel", stopDrag);
}

// A drag that already resized or toggled must not toggle again on its closing click.
function onClick() {
	if (!dragged) emit("toggle");
}
</script>
