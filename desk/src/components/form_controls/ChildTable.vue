<template>
	<div class="flex flex-col">
		<div class="mb-1.5 text-xs text-gray-600">{{ label }}</div>

		<div class="min-w-full rounded border border-gray-100">
			<!-- Header -->
			<div
				class="grid items-center rounded-t bg-gray-100"
				:style="{
					gridTemplateColumns:
						'1fr ' + fields.map((col) => (col.width || 2) + 'fr').join(' ') + ' 1fr',
				}"
			>
				<div class="border-r p-2 text-center text-base text-gray-900">No.</div>
				<div class="border-r p-2 text-base text-gray-900" v-for="field in fields" :key="field.name">
					{{ field.label }}
				</div>
				<div class="p-2 text-center text-base text-gray-900"></div>
			</div>

			<!-- Rows -->
			<div
				v-for="(row, index) in rows"
				:key="row.name"
				class="grid-row grid items-center border-b border-gray-100 bg-white last:rounded-b last:border-b-0"
				:style="{
					gridTemplateColumns:
						'1fr ' + fields.map((col) => (col.width || 2) + 'fr').join(' ') + ' 1fr',
				}"
			>
				<div class="flex h-full justify-center border-r p-2 text-sm text-gray-800">
					{{ index + 1 }}
				</div>
				<div class="border-r border-gray-100" v-for="field in fields" :key="field.name">
					<FormControl
						:type="field.type"
						variant="outline"
						size="md"
						v-model="row[field.key]"
						class="text-sm text-gray-800"
					/>
				</div>
				<button @click="" class="flex justify-center">
					<FeatherIcon name="edit-2" class="h-3 w-3 text-gray-800" />
				</button>
			</div>
		</div>

		<div class="mt-2 flex flex-row">
			<Button size="sm" label="Add Row" />
		</div>
	</div>
</template>

<script setup>
import { FormControl, FeatherIcon } from "frappe-ui"

const props = defineProps({
	label: {
		type: String,
		required: true,
	},
	fields: {
		type: Array,
		required: true,
	},
	rows: {
		type: Array,
		required: true,
	},
})
</script>

<style>
/* TODO: get rid of forced styles for fields rendered inside grid */
/* For Input fields */
.grid-row input {
	border: none;
	border-radius: 0;
}

.grid-row input:focus,
.grid-row input:hover {
	box-shadow: none;
}

.grid-row input:focus-within {
	border: 1px solid #d1d8dd;
}

/* For Autocomplete */
.grid-row button {
	border: none;
	border-radius: 0;
	background-color: white;
}
</style>
