<!-- One column of a section: its fields, which drag within it and to any other column, the tray
     or a tab's name. A section of two columns or more shows each column's grip and "⋯". -->
<template>
	<div
		class="group/column relative flex min-w-0 flex-col"
		:class="{ 'rounded-6 ring-1 ring-outline-gray-4': selected }"
		:data-canvas-column="column.name"
		:data-canvas-selected="selected || undefined"
	>
		<RuleMark class="absolute -left-4 top-0" :canvas="canvas" kind="column" :node="column" />
		<div
			v-if="canvas.editable && section.columns.length > 1"
			class="mb-1 flex h-5 items-center gap-0.5 opacity-0 group-hover/column:opacity-100"
			:class="{ '!opacity-100': selected }"
			@click.stop="select"
		>
			<span
				class="column-grip flex size-5 cursor-grab items-center justify-center text-ink-gray-4 hover:text-ink-gray-7"
				:title="__('Drag to move the column')"
			>
				<span class="lucide-grip-horizontal size-4" aria-hidden="true" />
			</span>
			<Dropdown :options="menu" side="bottom" align="start">
				<Button
					variant="ghost"
					size="sm"
					class="!h-5 !w-5"
					icon="lucide-ellipsis"
					:aria-label="__('Column actions')"
				/>
			</Dropdown>
		</div>
		<Draggable
			:model-value="fieldnames"
			:item-key="(fieldname: string) => fieldname"
			group="canvas-fields"
			class="flex min-w-0 flex-1 flex-col gap-4 pb-4"
			:class="{ 'min-h-[60px]': !fieldnames.length }"
			:data-canvas-empty="!fieldnames.length || undefined"
			ghost-class="canvas-drop-line"
			v-bind="DRAG_OPTIONS"
			:disabled="!canvas.editable"
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
import { computed } from "vue";
import { Button, Dropdown } from "frappe-ui";
import Draggable from "vuedraggable";
import { __ } from "@/i18n";
import type { LayoutTreeColumn, LayoutTreeSection } from "./layoutTree";
import CanvasField from "./CanvasField.vue";
import { DRAG_OPTIONS, dropField } from "./canvasDrops";
import { canvasMenu, selectOn } from "./canvasMenu";
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
	props.column.fields.map((entry) => (typeof entry === "string" ? entry : entry.fieldname))
);
const selected = computed(() => {
	const selection = props.canvas.selection.value;
	return (
		selection?.kind === "column" &&
		selection.section === item.value.section &&
		selection.column === item.value.column
	);
});
const menu = computed(() => canvasMenu(props.canvas, item.value));

function select() {
	selectOn(props.canvas, item.value);
}
</script>
