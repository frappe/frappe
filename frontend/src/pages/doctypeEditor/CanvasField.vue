<!-- One field on the canvas, drawn by the record page's own control on an inert form. A click
     selects it and a drag moves it; its marks sit in the control's label, after the last word. -->
<template>
	<div
		class="group/field relative -m-1.5 rounded-6 p-1.5"
		:class="[
			selected ? 'ring-1 ring-outline-gray-5' : 'hover:ring-1 hover:ring-outline-gray-2',
			{ 'cursor-grab active:cursor-grabbing': editable },
		]"
		:data-canvas-field="fieldname"
		:data-canvas-selected="selected || undefined"
		@click.stop="selectOn(canvas, { kind: 'field', fieldname })"
	>
		<div
			v-if="node && panelRows"
			class="grid grid-cols-[130px_1fr] items-center gap-2"
			:class="{ 'opacity-50': hidden }"
			data-canvas-panel-row
		>
			<span class="truncate text-base text-ink-gray-5">
				{{ label }}<FieldMarks :canvas="canvas" :fieldname="fieldname" />
			</span>
			<span class="truncate text-base text-ink-gray-4">{{ __("Add {0}…", [label]) }}</span>
		</div>
		<div v-else-if="table" class="pointer-events-none" :class="{ 'opacity-50': hidden }" inert>
			<CanvasTable :field="table">
				<template #label-after
					><FieldMarks :canvas="canvas" :fieldname="fieldname"
				/></template>
			</CanvasTable>
		</div>
		<div v-else-if="node" class="pointer-events-none" :class="{ 'opacity-50': hidden }" inert>
			<FormLayoutField :field="node">
				<template #label-after
					><span v-if="node.fieldtype === 'HTML'" class="mr-2 text-sm text-ink-gray-6">{{
						label
					}}</span
					><FieldMarks :canvas="canvas" :fieldname="fieldname"
				/></template>
			</FormLayoutField>
		</div>
		<div v-else class="flex h-7 items-center text-base text-ink-gray-5">{{ fieldname }}</div>
		<p
			v-for="error in canvas.errorsAt('field', fieldname)"
			:key="error"
			class="mt-1 text-p-sm text-ink-red-4"
			data-canvas-error
		>
			{{ error }}
		</p>
		<span
			v-if="editable"
			class="pointer-events-none absolute right-1 top-1 grid size-5 place-items-center rounded-4 bg-surface-base text-ink-gray-4 opacity-0 group-hover/field:opacity-100"
			:class="{ '!opacity-100': selected }"
			data-canvas-controls
			aria-hidden="true"
		>
			<span class="lucide-grip-vertical size-4" />
		</span>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { FormLayoutField, mapField } from "@framework/ui/FormLayout";
import { __ } from "@/i18n";
import CanvasTable from "./CanvasTable.vue";
import { selectOn } from "./canvasMenu";
import type { DesignCanvas } from "./designCanvas";
import { TABLE_TYPES } from "./fieldtypes";
import { usePanelRows } from "./inertForm";
import FieldMarks from "./FieldMarks.vue";

const props = defineProps<{ canvas: DesignCanvas; fieldname: string }>();

const panelRows = usePanelRows();
const editable = computed(() => props.canvas.editable);
const selected = computed(() => {
	const selection = props.canvas.selection.value;
	return selection?.kind === "field" && selection.fieldname === props.fieldname;
});
const hidden = computed(() => Boolean(props.canvas.customize?.marks(props.fieldname).hidden));
const node = computed(() => {
	const field = props.canvas.field(props.fieldname);
	return field ? mapField(field, {}) : null;
});
const table = computed(() => {
	const field = props.canvas.field(props.fieldname);
	return field && TABLE_TYPES.includes(field.fieldtype) ? field : null;
});
const label = computed(() => {
	const field = props.canvas.field(props.fieldname);
	return field?.label ? __(field.label, [], props.canvas.state.doctype) : props.fieldname;
});
</script>
