<template>
	<RecordTable
		v-if="isTable(value)"
		:columns="columnsOf(value)"
		:rows="value.map((cells) => ({ cells }))"
		:tall="nested"
	/>
	<div v-else-if="Array.isArray(value)" class="flex flex-col gap-0.5">
		<DataView v-for="(item, i) in value" :key="i" :value="item" nested />
	</div>
	<table v-else-if="value !== null && typeof value === 'object'" class="border-collapse text-left">
		<tbody>
			<tr v-for="[field, part] in Object.entries(value)" :key="field" class="align-top">
				<td class="whitespace-nowrap py-0.5 pr-3 text-ink-gray-5">{{ humanize(field) }}</td>
				<td class="py-0.5">
					<div
						v-if="isTable(part)"
						class="my-0.5 overflow-hidden rounded-[6px] border border-outline-gray-1"
					>
						<DataView :value="part" nested />
					</div>
					<DataView v-else :value="part" nested />
				</td>
			</tr>
		</tbody>
	</table>
	<span v-else class="whitespace-pre-wrap break-words">{{ cellText(value) }}</span>
</template>

<script setup>
import RecordTable from "./RecordTable.vue";
import { cellText, columnsOf, humanize, isTable } from "./result.js";

// Any value in words, by its shape: records as a table, a record as a line per field,
// a list as a line per item. Each part is drawn the same way, however deep.
defineProps({
	value: { default: null },
	// a part of a larger value, whose box scrolls already
	nested: { type: Boolean, default: false },
});
</script>
