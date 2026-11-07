<template>
	<RecordTable :columns="columns" :rows="rows" :doctype="doctype" />
</template>

<script setup>
import { computed } from "vue";

import RecordTable from "./RecordTable.vue";
import { columnsOf, parseResult } from "./result.js";

const props = defineProps({
	arguments: { type: Object, required: true },
	result: { type: Object, default: null },
});

const records = computed(() => props.arguments.records ?? []);
const doctype = computed(() => props.arguments.doctype ?? "");
const columns = computed(() => columnsOf(records.value));

// Names come back in the order of the records.
const rows = computed(() => {
	const parsed = parseResult(props.result);
	if (!parsed) return records.value.map((cells) => ({ cells }));
	return records.value.map((cells, row) => ({ cells, status: { name: parsed.created?.[row] } }));
});
</script>
