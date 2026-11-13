<!-- One field on the canvas, drawn by the record page's own control on an inert form. A click
     selects it, a drag moves it, and its "⋯" holds the keyboard moves. -->
<template>
	<div
		class="group/field relative -m-2 rounded-6 p-2"
		:class="[
			selected ? 'ring-1 ring-outline-gray-4' : 'hover:ring-1 hover:ring-outline-gray-2',
			{ 'cursor-grab active:cursor-grabbing': editable },
		]"
		:data-canvas-field="fieldname"
		:data-canvas-selected="selected || undefined"
		@click.stop="acts.perform('canvas.select', { kind: 'field', fieldname })"
	>
		<div
			v-if="node && panelRows"
			class="grid grid-cols-[130px_1fr] items-center gap-2"
			:class="{ 'opacity-50': hidden }"
			data-canvas-panel-row
		>
			<span class="truncate text-base text-ink-gray-5">{{ label }}</span>
			<span class="truncate text-base text-ink-gray-4">{{ __("Add {0}…", [label]) }}</span>
		</div>
		<div v-else-if="table" class="pointer-events-none" :class="{ 'opacity-50': hidden }" inert>
			<CanvasTable :field="table" />
		</div>
		<div v-else-if="node" class="pointer-events-none" :class="{ 'opacity-50': hidden }" inert>
			<FormLayoutField :field="node" />
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
		<div class="absolute right-1 top-0.5 flex h-5 items-center gap-1">
			<RuleMark :canvas="canvas" kind="field" :node="canvas.field(fieldname)" />
			<div
				v-if="editable"
				class="flex items-center gap-0.5 rounded-4 bg-surface-base opacity-0 group-hover/field:opacity-100"
				:class="{ '!opacity-100': selected }"
				data-canvas-controls
			>
				<Dropdown :options="menu" side="bottom" align="end">
					<Button
						variant="ghost"
						size="sm"
						class="!h-5 !w-5"
						icon="lucide-ellipsis"
						:aria-label="__('Field actions')"
					/>
				</Dropdown>
				<span
					class="lucide-grip-vertical size-4 text-ink-gray-4"
					:title="__('Drag to move the field')"
					aria-hidden="true"
				/>
			</div>
			<CustomizeMarks :canvas="canvas" :fieldname="fieldname" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Dropdown } from "frappe-ui";
import { FormLayoutField, mapField } from "@framework/ui/FormLayout";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import CanvasTable from "./CanvasTable.vue";
import { canvasMenu } from "./canvasMenu";
import CustomizeMarks from "./CustomizeMarks.vue";
import type { DesignCanvas } from "./designCanvas";
import { usePanelRows } from "./inertForm";
import RuleMark from "./RuleMark.vue";

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
	return field?.fieldtype === "Table" ? field : null;
});
const label = computed(() => {
	const field = props.canvas.field(props.fieldname);
	return field?.label ? __(field.label, [], props.canvas.state.doctype) : props.fieldname;
});
const menu = computed(() =>
	canvasMenu(props.canvas, { kind: "field", fieldname: props.fieldname })
);
</script>
