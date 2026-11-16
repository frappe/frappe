<!-- The menu at a right-click on the canvas, over the item it was made on. -->
<template>
	<ContextMenu :options="options" @update:open="$event || closeContextMenu(canvas)">
		<div class="fixed size-0" :style="{ left: `${at.x}px`, top: `${at.y}px` }" ref="anchor" />
	</ContextMenu>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { ContextMenu } from "frappe-ui";
import { canvasMenu } from "./canvasMenu";
import { closeContextMenu, type ContextMenuAt } from "./canvasContextMenu";
import type { DesignCanvas } from "./designCanvas";

const props = defineProps<{ canvas: DesignCanvas; at: ContextMenuAt }>();

const anchor = ref<HTMLElement>();
const options = computed(() => canvasMenu(props.canvas, props.at.item));

// The menu opens where a contextmenu event lands, so the anchor replays one at the pointer.
watch(
	() => props.at,
	async (at) => {
		await nextTick();
		anchor.value?.dispatchEvent(
			new MouseEvent("contextmenu", {
				bubbles: true,
				cancelable: true,
				clientX: at.x,
				clientY: at.y,
			})
		);
	},
	{ immediate: true }
);
</script>
