<!-- One section on the canvas: its label typed in place, its columns of fields, and "Add field".
     Every section shows open, whatever its collapse settings say. -->
<template>
	<div
		class="group/section relative -m-3 rounded-7 p-3"
		:class="{ 'ring-1 ring-outline-gray-5': selected }"
		:data-canvas-section="section.name"
		:data-canvas-selected="selected || undefined"
		@click.stop="select({ kind: 'section', section: name })"
	>
		<div class="relative z-[1] mb-4 flex h-7 items-center gap-1">
			<input
				:value="section.label ?? ''"
				:placeholder="__('Untitled section')"
				:readonly="!canvas.editable"
				class="min-w-[8ch] max-w-full border-0 [field-sizing:content] bg-transparent p-0 text-base-medium text-ink-gray-9 placeholder:font-normal placeholder:text-ink-gray-4 focus:outline-none focus:ring-0"
				:aria-label="__('Section label')"
				data-canvas-section-label
				@focus="select({ kind: 'section', section: name })"
				@keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
				@change="setLabel(($event.target as HTMLInputElement).value)"
			/>
			<RuleMark :canvas="canvas" kind="section" :node="section" />
			<div
				v-if="canvas.editable"
				class="absolute right-0 top-0 flex items-center rounded-4 bg-surface-base opacity-0 group-focus-within/section:opacity-100 group-hover/section:opacity-100"
				:class="{ '!opacity-100': selected }"
				data-canvas-controls
			>
				<Dropdown :options="menu" side="bottom" align="end">
					<Button
						variant="ghost"
						size="sm"
						icon="lucide-ellipsis"
						:aria-label="__('Section actions')"
					/>
				</Dropdown>
				<span
					class="section-grip flex size-7 shrink-0 cursor-grab items-center justify-center text-ink-gray-4 hover:text-ink-gray-7"
					:title="__('Drag to move the section')"
				>
					<span class="lucide-grip-vertical size-4" aria-hidden="true" />
				</span>
			</div>
		</div>
		<p
			v-for="error in canvas.errorsAt('container', name)"
			:key="error"
			class="relative z-[1] mb-3 text-p-sm text-ink-red-4"
			data-canvas-error
		>
			{{ error }}
		</p>
		<Draggable
			:model-value="section.columns"
			:item-key="(column: LayoutTreeColumn) => column.name"
			group="canvas-columns"
			handle=".column-grip"
			class="grid auto-cols-fr grid-flow-col gap-x-4"
			ghost-class="opacity-40"
			v-bind="DRAG_OPTIONS"
			:disabled="!canvas.editable"
			@change="dropColumn(canvas, $event, name)"
		>
			<template #item="{ element: column }">
				<CanvasColumn :canvas="canvas" :section="section" :column="column" />
			</template>
		</Draggable>
		<AddFieldRow v-if="canvas.editable" class="mt-1" :canvas="canvas" :section="name" />
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Dropdown } from "frappe-ui";
import Draggable from "vuedraggable";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { LayoutTreeColumn, LayoutTreeSection } from "./layoutTree";
import AddFieldRow from "./AddFieldRow.vue";
import CanvasColumn from "./CanvasColumn.vue";
import { DRAG_OPTIONS, dropColumn } from "./canvasDrops";
import { canvasMenu, selectOn } from "./canvasMenu";
import type { CanvasSelection, DesignCanvas } from "./designCanvas";
import RuleMark from "./RuleMark.vue";

const props = defineProps<{ canvas: DesignCanvas; section: LayoutTreeSection }>();

const name = computed(() => props.section.name!);
const selected = computed(() => {
	const selection = props.canvas.selection.value;
	return selection?.kind === "section" && selection.section === name.value;
});
const menu = computed(() => canvasMenu(props.canvas, { kind: "section", section: name.value }));

function select(selection: CanvasSelection) {
	selectOn(props.canvas, selection);
}

function setLabel(label: string) {
	if (label.trim() === (props.section.label ?? "")) return;
	void acts.perform("canvas.set_container_property", {
		container: name.value,
		property: "label",
		value: label.trim(),
	});
}
</script>
