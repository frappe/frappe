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
		<div v-if="node" class="pointer-events-none" inert>
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
		<RuleMark
			class="absolute right-12 top-0.5"
			:canvas="canvas"
			kind="field"
			:node="canvas.field(fieldname)"
		/>
		<div
			v-if="editable"
			class="absolute right-1 top-0.5 flex h-5 items-center gap-0.5 rounded-4 bg-surface-base opacity-0 group-hover/field:opacity-100"
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
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Dropdown } from "frappe-ui";
import { FormLayoutField, mapField } from "@framework/ui/FormLayout";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { canvasMenu } from "./canvasMenu";
import type { DesignCanvas } from "./designCanvas";
import RuleMark from "./RuleMark.vue";

const props = defineProps<{ canvas: DesignCanvas; fieldname: string }>();

const editable = computed(() => props.canvas.editable);
const selected = computed(() => {
	const selection = props.canvas.selection.value;
	return selection?.kind === "field" && selection.fieldname === props.fieldname;
});
const node = computed(() => {
	const field = props.canvas.field(props.fieldname);
	return field ? mapField(field, {}) : null;
});
const menu = computed(() =>
	canvasMenu(props.canvas, { kind: "field", fieldname: props.fieldname })
);
</script>
