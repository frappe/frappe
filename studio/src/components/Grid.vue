<template>
	<div class="flex flex-col">
		<div v-if="label" class="mb-1.5 text-xs text-gray-600">{{ label }}</div>

		<div class="rounded border border-gray-100">
			<!-- Header -->
			<div
				class="grid items-center rounded-t-sm bg-gray-100"
				:style="{ gridTemplateColumns: gridTemplateColumns }"
			>
				<div class="border-r p-1 text-center">
					<Checkbox
						size="sm"
						class="cursor-pointer duration-300"
						:modelValue="allRowsSelected"
						@click.stop="toggleSelectAllRows($event.target.checked)"
					/>
				</div>
				<div class="inline-flex h-full items-center justify-center border-r p-1 text-base text-gray-800">
					No.
				</div>
				<div
					class="inline-flex h-full items-center border-r p-1 text-base text-gray-800"
					v-for="column in columns"
					:key="column.fieldname"
				>
					{{ column.label }}
				</div>
				<div class="p-1 text-center text-base text-gray-900"></div>
			</div>

			<!-- Rows -->
			<template v-if="rows.length">
				<Draggable class="w-full" v-model="rows" group="rows" item-key="name">
					<template #item="{ element: row, index }">
						<div
							class="grid-row grid cursor-pointer items-center border-b border-gray-100 bg-white last:rounded-b last:border-b-0"
							:style="{ gridTemplateColumns: gridTemplateColumns }"
						>
							<div class="border-r text-center">
								<Checkbox
									size="sm"
									class="cursor-pointer duration-300"
									:modelValue="selectedRows.has(row.name)"
									@click.stop="toggleSelectRow(row)"
								/>
							</div>
							<div class="flex h-full items-center justify-center border-r p-1 text-sm text-gray-800">
								{{ index + 1 }}
							</div>
							<div class="border-r border-gray-100" v-for="column in columns" :key="column.fieldname">
								<Link
									v-if="column.fieldtype === 'Link'"
									:doctype="row.link_type"
									v-model="row[column.fieldname]"
									class="text-sm text-gray-800"
									@update:modelValue="(e) => column.onChange && column.onChange(e, index)"
								/>
								<FormControl
									v-else
									:type="column.fieldtype.toLowerCase()"
									:options="column.options"
									variant="outline"
									size="md"
									v-model="row[column.fieldname]"
									class="text-sm text-gray-800"
									@change="
										(e: Event) =>
											column.onChange && column.onChange((e.target as HTMLInputElement).value, index)
									"
								/>
							</div>
							<button @click="" class="flex items-center justify-center">
								<FeatherIcon name="edit-2" class="h-3 w-3 text-gray-800" />
							</button>
						</div>
					</template>
				</Draggable>
			</template>

			<div v-else class="flex flex-col items-center rounded p-5 text-sm text-gray-600">No Data</div>
		</div>

		<div class="mt-2 flex flex-row gap-2">
			<Button size="sm" variant="solid" theme="red" label="Delete" v-if="showDeleteBtn" @click="deleteRows" />
			<Button size="sm" label="Add Row" @click="addRow" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { reactive, computed } from "vue"
import { FormControl, Checkbox } from "frappe-ui"
import Draggable from "vuedraggable"

import Link from "@/components/Link.vue"
import { generateId } from "@/utils/helpers"
import type { GridColumn, GridRow } from "@/types/doctype"

const props = defineProps<{
	label?: string
	columns: GridColumn[]
}>()
const rows = defineModel("rows", {
	type: Array as () => GridRow[],
	default: () => [],
})
const selectedRows = reactive(new Set<string>())

const gridTemplateColumns = computed(() => {
	// for the checkbox & sr no. columns
	let columns = "0.75fr 0.75fr"
	columns += " " + props.columns.map((col) => `minmax(0, ${col.width || 2}fr)`).join(" ")
	// for the edit button column
	columns += " 0.75fr"

	return columns
})

const allRowsSelected = computed(() => {
	if (!rows.length) return false
	return rows.length === selectedRows.size
})

const showDeleteBtn = computed(() => selectedRows.size > 0)

const toggleSelectAllRows = (iSelected: boolean) => {
	if (iSelected) {
		rows.value.forEach((row: GridRow) => selectedRows.add(row.name))
	} else {
		selectedRows.clear()
	}
}

const toggleSelectRow = (row: GridRow) => {
	if (selectedRows.has(row.name)) {
		selectedRows.delete(row.name)
	} else {
		selectedRows.add(row.name)
	}
}

const addRow = () => {
	const newRow = {} as GridRow
	props.columns.forEach((column) => {
		newRow[column.fieldname] = ""
	})
	newRow.name = generateId()
	rows.value.push(newRow)
}

const deleteRows = () => {
	rows.value = rows.value.filter((row: GridRow) => !selectedRows.has(row.name))
	selectedRows.clear()
}
</script>

<style>
/* For Input fields */
.grid-row input:not([type="checkbox"]) {
	border: none;
	border-radius: 0;
	height: 40px;
}

.grid-row input:focus,
.grid-row input:hover {
	box-shadow: none;
}

.grid-row input:focus-within {
	border: 1px solid #d1d8dd;
}

/* For select field */
.grid-row select {
	border: none;
	border-radius: 0;
	height: 40px;
}

/* For Autocomplete */
.grid-row button {
	border: none;
	border-radius: 0;
	background-color: white;
	height: 40px;
}

.grid-row button:focus,
.grid-row button:hover {
	box-shadow: none;
	background-color: white;
}

.grid-row button:focus-within {
	border: 1px solid #d1d8dd;
}
</style>
