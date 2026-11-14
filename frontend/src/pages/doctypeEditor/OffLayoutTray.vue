<!-- "Fields not on this layout": the DocType's fields the Details layout does not place. A row
     drags onto the canvas or places with its button; a field dragged here leaves the layout. -->
<template>
	<div class="mt-10 border-t pt-4" data-canvas-tray>
		<button
			type="button"
			class="flex h-7 items-center gap-1.5 text-base-medium text-ink-gray-8"
			:aria-expanded="canvas.trayOpen.value"
			@click="canvas.trayOpen.value = !canvas.trayOpen.value"
		>
			<span
				class="size-4 text-ink-gray-5"
				:class="canvas.trayOpen.value ? 'lucide-chevron-down' : 'lucide-chevron-right'"
				aria-hidden="true"
			/>
			{{ __("Fields not on this layout") }}
			<span class="text-ink-gray-5">{{ rows.length }}</span>
		</button>
		<Draggable
			v-show="canvas.trayOpen.value"
			:model-value="fieldnames"
			:item-key="(fieldname: string) => fieldname"
			:group="{ name: 'canvas-fields', pull: 'clone', put: (_to: unknown, from: { el: HTMLElement }) => canvas.editable && !from.el.hasAttribute('data-new-field-types') }"
			:sort="false"
			class="mt-2 flex min-h-8 flex-col"
			ghost-class="canvas-drop-line"
			v-bind="DRAG_OPTIONS"
			:disabled="!canvas.editable"
			data-canvas-tray-list
			@change="dropOffLayout"
		>
			<template #item="{ element: fieldname }">
				<div
					class="group/row -mx-2 flex h-8 items-center gap-2 rounded-4 px-2"
					:class="[
						isSelected(fieldname)
							? 'ring-1 ring-outline-gray-4'
							: 'hover:bg-surface-gray-2',
						{ 'cursor-grab active:cursor-grabbing': canvas.editable },
					]"
					:data-canvas-tray-field="fieldname"
					:data-canvas-selected="isSelected(fieldname) || undefined"
					@click.stop="acts.perform('canvas.select', { kind: 'field', fieldname })"
				>
					<span class="min-w-0 truncate text-base text-ink-gray-8">{{
						label(fieldname)
					}}</span>
					<span class="shrink-0 text-sm text-ink-gray-5">{{
						__(byName[fieldname].field.fieldtype)
					}}</span>
					<Badge
						v-if="byName[fieldname].new"
						theme="gray"
						:label="__('New since the save')"
					/>
					<Badge
						v-if="byName[fieldname].asked"
						theme="gray"
						:label="__('Asked for on save')"
					/>
					<Button
						v-if="canvas.editable"
						class="ml-auto opacity-0 group-hover/row:opacity-100"
						variant="ghost"
						size="sm"
						:label="__('Place')"
						@click.stop="place(fieldname)"
					/>
				</div>
			</template>
		</Draggable>
		<p
			v-if="canvas.trayOpen.value && !rows.length"
			class="pointer-events-none -mt-8 flex h-8 items-center text-base text-ink-gray-5"
		>
			{{ __("Every field is on this layout.") }}
		</p>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Badge, Button } from "frappe-ui";
import Draggable from "vuedraggable";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { DRAG_OPTIONS, dropOffLayout } from "./canvasDrops";
import type { DesignCanvas } from "./designCanvas";

const props = defineProps<{ canvas: DesignCanvas }>();

const rows = computed(() => props.canvas.offLayout.value);
const fieldnames = computed(() => rows.value.map((row) => row.field.fieldname));
const byName = computed(() =>
	Object.fromEntries(rows.value.map((row) => [row.field.fieldname, row]))
);

function label(fieldname: string) {
	const { label } = byName.value[fieldname].field;
	return label ? __(label, [], props.canvas.state.doctype) : fieldname;
}

function isSelected(fieldname: string) {
	const selection = props.canvas.selection.value;
	return selection?.kind === "field" && selection.fieldname === fieldname;
}

function place(fieldname: string) {
	const section = props.canvas.targetSection();
	const into = section
		? props.canvas.addPlace(section)
		: { tab: props.canvas.openTab.value?.name };
	void acts.perform("canvas.place_field", { fieldname, ...into });
}
</script>
