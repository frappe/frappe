<template>
	<div class="flex flex-col gap-2">
		<div v-if="label" class="text-sm text-ink-gray-5">
			{{ label }}
			<span v-if="required" class="text-ink-red-2">*</span>
		</div>

		<div v-if="columns.length" class="overflow-hidden rounded border border-outline-gray-2">
			<!-- Header -->
			<div class="flex items-stretch bg-surface-gray-2 text-sm text-ink-gray-5">
				<div
					class="flex w-10 shrink-0 items-center justify-center border-r border-outline-gray-2 py-2"
				>
					#
				</div>
				<div class="grid flex-1" :style="{ gridTemplateColumns }">
					<div
						v-for="col in columns"
						:key="col.fieldname"
						class="truncate border-r border-outline-gray-2 px-2 py-2 last:border-r-0"
						:title="col.label"
					>
						{{ col.label ?? col.fieldname }}
						<span v-if="col.reqd" class="text-ink-red-2">*</span>
					</div>
				</div>
				<div v-if="!disabled" class="w-20 shrink-0" />
			</div>

			<!-- Rows -->
			<template v-if="rows.length">
				<div
					v-for="(row, rowIndex) in rows"
					:key="rowIndex"
					class="flex items-stretch border-t border-outline-gray-2 bg-surface-white"
				>
					<div
						class="flex w-10 shrink-0 items-center justify-center border-r border-outline-gray-2 py-2 text-sm text-ink-gray-7"
					>
						{{ rowIndex + 1 }}
					</div>
					<div class="grid flex-1" :style="{ gridTemplateColumns }">
						<div
							v-for="col in columns"
							:key="col.fieldname"
							class="flex min-w-0 items-center border-r border-outline-gray-2 px-2 py-1 last:border-r-0"
						>
							<slot
								name="cell"
								:row="row"
								:column="col"
								:index="rowIndex"
								:value="row[col.fieldname]"
								:update="(v: any) => updateCell(rowIndex, col, v)"
								:commit="(v: any) => commitCell(rowIndex, col, v)"
							>
								<span class="truncate text-sm text-ink-gray-7">
									{{ row[col.fieldname] }}
								</span>
							</slot>
						</div>
					</div>
					<div
						v-if="!disabled"
						class="flex w-20 shrink-0 items-center justify-center gap-1"
					>
						<Button
							variant="ghost"
							icon="lucide-chevron-up"
							:disabled="rowIndex === 0"
							@click="moveRow(rowIndex, -1)"
						/>
						<Button
							variant="ghost"
							icon="lucide-trash-2"
							@click="deleteRow(rowIndex)"
						/>
					</div>
				</div>
			</template>

			<div
				v-else
				class="border-t border-outline-gray-2 p-4 text-center text-sm text-ink-gray-4"
			>
				No rows
			</div>
		</div>

		<!-- No columns to render (e.g. child meta absent). -->
		<div v-else class="text-sm text-ink-gray-4">No columns to display</div>

		<div v-if="!disabled && columns.length">
			<Button label="Add Row" icon-left="lucide-plus" @click="addRow" />
		</div>
	</div>
</template>

<script setup lang="ts" generic="T extends GridColumn">
import { computed } from "vue";
import { Button } from "frappe-ui";
import type { GridCellSlotProps, GridColumn, GridEmits } from "./types";

const props = defineProps<{
	/** Columns to render, in order. */
	columns: T[];
	/** Disable structural actions (add/delete/reorder) and render read-only. */
	disabled?: boolean;
	/** Optional heading shown above the grid. */
	label?: string;
	/** Renders a `*` next to the label. */
	required?: boolean;
}>();

const emit = defineEmits<GridEmits>();

// `v-model` for the rows array. The slot's `update` writes it (live sync);
// `commit` additionally emits `change`.
const rows = defineModel<Record<string, any>[]>({ default: () => [] });

defineSlots<{
	/** Render/edit one cell. Falls back to plain text when not provided. */
	cell(props: GridCellSlotProps<T>): any;
}>();

const gridTemplateColumns = computed(() => `repeat(${props.columns.length}, minmax(0, 1fr))`);

// Every mutation produces a new array (and a fresh row object for edits) rather
// than mutating in place — clean reactivity, no surprise aliasing for the parent
// that owns the value.
function withRow(index: number, row: Record<string, any>) {
	const next = rows.value.slice();
	next[index] = row;
	return next;
}

function updateCell(index: number, col: T, value: any) {
	rows.value = withRow(index, { ...rows.value[index], [col.fieldname]: value });
}

function commitCell(index: number, col: T, value: any) {
	const next = withRow(index, { ...rows.value[index], [col.fieldname]: value });
	rows.value = next;
	emit("change", next);
}

function addRow() {
	const next = [...rows.value, {}];
	rows.value = next;
	emit("change", next);
}

function deleteRow(index: number) {
	const next = rows.value.filter((_, i) => i !== index);
	rows.value = next;
	emit("change", next);
}

function moveRow(index: number, delta: number) {
	const target = index + delta;
	if (target < 0 || target >= rows.value.length) return;
	const next = rows.value.slice();
	[next[index], next[target]] = [next[target], next[index]];
	rows.value = next;
	emit("change", next);
}
</script>
