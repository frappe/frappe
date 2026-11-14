<!-- The "Drop here to remove" pill, sticky at the canvas's bottom while a placed field is dragged.
     Sortable's fallback drag hides the pointer from the page's lists, so the bin tracks the pointer itself. -->
<template>
	<div
		class="pointer-events-none sticky bottom-6 !z-[100001] flex h-0 justify-center"
		aria-hidden="true"
	>
		<div
			ref="bin"
			class="flex h-9 -translate-y-full items-center gap-2 rounded-8 border px-4 text-base shadow-xl transition-[opacity,background-color,border-color,color] duration-150"
			:class="[
				canvas.drag.value.active ? 'opacity-100' : 'opacity-0',
				canvas.drag.value.overBin
					? 'border-outline-red-5 bg-surface-red-2 text-ink-red-7'
					: 'border-outline-gray-5 bg-surface-base text-ink-gray-6',
			]"
			:data-over="canvas.drag.value.overBin || undefined"
			data-canvas-bin
		>
			<span class="lucide-trash-2 size-4" />
			<!-- Both phrases share one cell, so the pill keeps its width when the pointer enters it. -->
			<span class="grid">
				<span
					v-for="phrase in phrases"
					:key="phrase"
					class="col-start-1 row-start-1"
					:class="{ invisible: phrase !== words }"
					>{{ phrase }}</span
				>
			</span>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { takesOff } from "./fieldPanel";

const props = defineProps<{ canvas: DesignCanvas }>();
const bin = ref<HTMLElement>();
const MARGIN = 8;

// What the drop does follows the panel trash: off the layout, hide in Customize, else remove.
const phrases = computed(() => {
	const { fieldname } = props.canvas.drag.value;
	if (takesOff(props.canvas)) return [__("Drop here to take off"), __("Release to take off")];
	if (fieldname && props.canvas.customize?.hidesOnRemove(fieldname)) {
		return [__("Drop here to hide"), __("Release to hide")];
	}
	return [__("Drop here to remove"), __("Release to remove")];
});
const words = computed(() => phrases.value[props.canvas.drag.value.overBin ? 1 : 0]);

function track(event: PointerEvent) {
	const { drag } = props.canvas;
	if (!drag.value.active || !bin.value) return;
	const box = bin.value.getBoundingClientRect();
	const over =
		event.clientX >= box.left - MARGIN &&
		event.clientX <= box.right + MARGIN &&
		event.clientY >= box.top - MARGIN &&
		event.clientY <= box.bottom + MARGIN;
	if (over !== drag.value.overBin) drag.value = { ...drag.value, overBin: over };
}

// Only a drag in flight needs the pointer.
watch(
	() => props.canvas.drag.value.active,
	(active) => {
		if (active) window.addEventListener("pointermove", track, true);
		else window.removeEventListener("pointermove", track, true);
	},
	{ immediate: true }
);
onBeforeUnmount(() => window.removeEventListener("pointermove", track, true));
</script>
