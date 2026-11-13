<!-- The child editor's Grid columns group: a bar of the columns' widths against the form's, then one
     row per column (drag to reorder, − n + for its width, × to take it off), then Add column. -->
<template>
	<PanelSection :label="__('Grid columns')" :count="columns.length" data-grid-columns>
		<div class="flex flex-col gap-1.5">
			<div class="relative h-2">
				<div class="flex h-full gap-0.5 overflow-hidden rounded-full bg-surface-gray-2">
					<div
						v-for="field in columns"
						:key="field.fieldname"
						class="h-full min-w-0"
						:class="selected(field) ? 'bg-surface-gray-7' : 'bg-surface-gray-5'"
						:style="{ flex: `${columnWidth(field)} 1 0` }"
					/>
					<div
						v-if="!fit.over && columns.length"
						:style="{ flex: `${fit.room - fit.used} 1 0` }"
					/>
				</div>
				<div
					v-if="fit.over"
					class="absolute -inset-y-0.5 w-0.5 -translate-x-1/2 rounded-full bg-surface-gray-9"
					:style="{ left: `${(fit.room / fit.used) * 100}%` }"
					data-form-edge
				/>
			</div>
			<p class="text-p-sm text-ink-gray-5" data-grid-fit>{{ fitLine }}</p>
			<p v-if="shared" class="text-p-sm text-ink-gray-5" data-shared-child>{{ shared }}</p>
		</div>
		<Draggable
			:model-value="columns"
			item-key="fieldname"
			handle="[data-column-handle]"
			:animation="120"
			class="-mx-2 flex flex-col"
			ghost-class="opacity-40"
			@end="moved"
		>
			<template #item="{ element: field }">
				<div
					class="group/column flex h-8 items-center gap-1 rounded-4 pl-1 pr-0.5 hover:bg-surface-gray-2"
					:class="{ 'bg-surface-gray-2': selected(field) }"
					:data-grid-column="field.fieldname"
				>
					<span
						class="lucide-grip-vertical size-4 shrink-0 cursor-grab text-ink-gray-4"
						data-column-handle
						:title="__('Drag to move the column')"
						aria-hidden="true"
					/>
					<button
						type="button"
						class="flex h-8 min-w-0 flex-1 items-center text-left text-base text-ink-gray-8"
						@click="
							acts.perform('canvas.select', {
								kind: 'field',
								fieldname: field.fieldname,
							})
						"
					>
						<span class="truncate">{{ field.label || field.fieldname }}</span>
					</button>
					<div
						class="flex shrink-0 items-center rounded-4 bg-surface-gray-2 group-hover/column:bg-surface-gray-3"
					>
						<Button
							variant="ghost"
							size="sm"
							icon="lucide-minus"
							:disabled="!width(field)"
							:aria-label="__('Narrower')"
							@click="grid.step(field, -1)"
						/>
						<Tooltip :text="__('{0}px in the grid', [columnWidth(field)])">
							<span
								class="w-9 text-center text-sm tabular-nums text-ink-gray-8"
								data-column-width
							>
								{{ width(field) || __("Auto") }}
							</span>
						</Tooltip>
						<Button
							variant="ghost"
							size="sm"
							icon="lucide-plus"
							:disabled="width(field) >= MAX_COLUMNS"
							:aria-label="__('Wider')"
							@click="grid.step(field, 1)"
						/>
					</div>
					<Tooltip :text="__('Take off the grid')">
						<Button
							variant="ghost"
							size="sm"
							icon="lucide-x"
							:aria-label="__('Take off the grid')"
							@click="grid.remove(field.fieldname)"
						/>
					</Tooltip>
				</div>
			</template>
		</Draggable>
		<div>
			<Dropdown :options="addMenu" side="bottom" align="start">
				<Button
					variant="subtle"
					size="sm"
					icon-left="lucide-plus"
					:label="__('Add column')"
					:disabled="!addMenu.length"
				/>
			</Dropdown>
		</div>
	</PanelSection>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
// @ts-ignore vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import { Button, Dropdown, Tooltip } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { CHILD_TABLES } from "./childTables";
import type { DesignCanvas } from "./designCanvas";
import { columnWidth, GridColumns, MAX_COLUMNS } from "./gridColumns";
import PanelSection from "./PanelSection.vue";

const props = defineProps<{ canvas: DesignCanvas }>();

const tables = inject(CHILD_TABLES, null);
const grid = new GridColumns(props.canvas);
const columns = grid.columns;
const fit = grid.fit;

const fitLine = computed(() => {
	const last = columns.value.at(-1);
	if (!last) return __("No columns yet. The grid shows the child's fields until one is added.");
	if (!fit.value.over) return __("Fits the form's width.");
	return __("Wider than the form: the grid scrolls sideways to show {0}.", [
		last.label || last.fieldname,
	]);
});

const shared = computed(() => {
	const parent = tables?.parentDoctype.value;
	const others = (props.canvas.state.parents ?? []).filter((one) => one !== parent);
	return others.length ? __("Shared: the same grid shows in {0}.", [others.join(", ")]) : "";
});

const addMenu = computed(() =>
	grid.candidates.value.map((field) => ({
		label: field.label || field.fieldname,
		onClick: () => grid.add(field.fieldname),
	}))
);

function width(field: RawMetaField) {
	return Number(field.columns) || 0;
}

function selected(field: RawMetaField) {
	const selection = props.canvas.selection.value;
	return selection?.kind === "field" && selection.fieldname === field.fieldname;
}

function moved(event: { oldIndex: number; newIndex: number }) {
	if (event.oldIndex === event.newIndex) return;
	grid.move(columns.value[event.oldIndex].fieldname, event.newIndex);
}
</script>
