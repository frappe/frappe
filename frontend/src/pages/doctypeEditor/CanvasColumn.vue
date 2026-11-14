<!-- One column of a section: its fields, which drag within it and to any other column, the tray
     or a tab's name. A click on its band (the free space around its fields: below the last one,
     between fields and in the gutter, minus the 6px each field claims for its own ring) selects it;
     hover rings it first, unless the section itself is selected. A section of two columns or more drags a ringed column by
     the grip on its ring's top edge. The band and ring take no space, so nothing moves. -->
<template>
	<div
		class="relative flex min-w-0 flex-col"
		:data-canvas-column="column.name"
		:data-canvas-selected="selected || undefined"
		@mouseover="hover($event)"
		@mouseleave="hovered = false"
		@click="selectBand($event)"
	>
		<div
			v-if="canvas.editable"
			class="absolute -top-4 bottom-0 -inset-x-2 rounded-8"
			data-canvas-column-band
		/>
		<div
			v-if="ringed"
			class="pointer-events-none absolute -top-2 bottom-2 -inset-x-2 z-[1] rounded-7 ring-1"
			:class="selected ? 'ring-outline-gray-5' : 'ring-outline-gray-3'"
			data-canvas-column-ring
		/>
		<span
			v-if="ringed && section.columns.length > 1"
			class="column-grip absolute -top-2 left-1/2 z-[2] flex h-4 -translate-x-1/2 -translate-y-1/2 cursor-grab items-center rounded-3 bg-surface-base px-1 text-ink-gray-5 hover:text-ink-gray-7"
			:title="__('Drag to move the column')"
			data-canvas-column-grip
		>
			<span class="lucide-grip-horizontal size-4" aria-hidden="true" />
		</span>
		<RuleMark
			class="absolute -left-6 top-0 z-[2]"
			:canvas="canvas"
			kind="column"
			:node="column"
		/>
		<Draggable
			:model-value="fieldnames"
			:item-key="(fieldname: string) => fieldname"
			group="canvas-fields"
			class="relative z-[1] flex min-w-0 flex-1 flex-col gap-4 pb-4"
			:class="{ 'min-h-[60px]': !fieldnames.length }"
			:data-canvas-empty="!fieldnames.length || undefined"
			ghost-class="canvas-drop-line"
			v-bind="DRAG_OPTIONS"
			:disabled="!canvas.editable"
			@start="startDrag(canvas, $event.item)"
			@end="dropOnBin(canvas)"
			@change="dropField(canvas, $event, { section: section.name!, column: column.name! })"
		>
			<template #item="{ element: fieldname }">
				<CanvasField :canvas="canvas" :fieldname="fieldname" />
			</template>
		</Draggable>
		<div
			v-if="!fieldnames.length"
			class="pointer-events-none absolute inset-x-0 bottom-4 flex h-[60px] items-center justify-center rounded-4 border border-dashed border-outline-gray-2 text-base text-ink-gray-4"
		>
			{{ __("Drop a field here") }}
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import Draggable from "vuedraggable";
import { __ } from "@/i18n";
import type { LayoutTreeColumn, LayoutTreeSection } from "./layoutTree";
import CanvasField from "./CanvasField.vue";
import { DRAG_OPTIONS, dropField, dropOnBin, startDrag } from "./canvasDrops";
import { selectOn } from "./canvasMenu";
import type { DesignCanvas } from "./designCanvas";
import RuleMark from "./RuleMark.vue";

const props = defineProps<{
	canvas: DesignCanvas;
	section: LayoutTreeSection;
	column: LayoutTreeColumn;
}>();

const item = computed(() => ({
	kind: "column" as const,
	section: props.section.name!,
	column: props.column.name!,
}));
const fieldnames = computed(() =>
	props.column.fields.map((entry) => (typeof entry === "string" ? entry : entry.fieldname)),
);
const selected = computed(() => {
	const selection = props.canvas.selection.value;
	return (
		selection?.kind === "column" &&
		selection.section === item.value.section &&
		selection.column === item.value.column
	);
});
const hovered = ref(false);
const sectionSelected = computed(() => {
	const selection = props.canvas.selection.value;
	return selection?.kind === "section" && selection.section === item.value.section;
});
// A field being dragged shows its own drop line; a hover ring beside it would read as a second target.
// A selected column keeps its ring: selection outlives a drag, as a selected field's ring does.
const dragging = computed(() => props.canvas.drag.value.active);
const ringed = computed(
	() =>
		props.canvas.editable &&
		(selected.value || (hovered.value && !sectionSelected.value && !dragging.value)),
);

// A field inside the column keeps its own hover ring and click.
function onField(event: Event) {
	return Boolean((event.target as HTMLElement).closest("[data-canvas-field]"));
}

function hover(event: MouseEvent) {
	hovered.value = !props.canvas.editable ? false : !onField(event);
}

function selectBand(event: MouseEvent) {
	if (!props.canvas.editable || onField(event)) return;
	event.stopPropagation();
	selectOn(props.canvas, item.value);
}
</script>
