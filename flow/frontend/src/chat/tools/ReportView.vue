<template>
	<RecordTable :columns="columns" :rows="rows" :footer="footer" :labels="labels" />
</template>

<script setup>
import { computed } from "vue";

import RecordTable from "./RecordTable.vue";
import { cellText, columnsOf, parseResult } from "./result.js";

const props = defineProps({
	arguments: { type: Object, required: true },
	result: { type: Object, default: null },
});

// Keyed by fieldname; labels are only headers.
const report = computed(() => parseResult(props.result));
const records = computed(() => report.value?.rows ?? []);
const total = computed(() => report.value?.total_row ?? null);
const labels = computed(() =>
	Object.fromEntries((report.value?.columns ?? []).map((c) => [c.fieldname, c.label]))
);
// report order; numeric keys would sort first
const columns = computed(() => {
	const filled = new Set(
		columnsOf(total.value ? [...records.value, total.value] : records.value)
	);
	return (report.value?.columns ?? []).map((c) => c.fieldname).filter((f) => filled.has(f));
});
// Frappe leaves the label out before a date column
const footer = computed(() => {
	const first = columns.value[0];
	if (!total.value || !first || cellText(total.value[first])) return total.value;
	return { ...total.value, [first]: "Total" };
});
const rows = computed(() => records.value.map((cells) => ({ cells })));
</script>
