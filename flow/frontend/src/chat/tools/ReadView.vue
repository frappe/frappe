<template>
	<RecordTable :columns="columns" :rows="rows" :doctype="doctype" link-column="name" />
</template>

<script setup>
import { computed } from "vue";

import RecordTable from "./RecordTable.vue";
import { columnsOf, parseResult } from "./result.js";

const props = defineProps({
	arguments: { type: Object, required: true },
	result: { type: Object, default: null },
});

const doctype = computed(() => props.arguments.doctype ?? "");
const records = computed(() => {
	const parsed = parseResult(props.result);
	return Array.isArray(parsed) ? parsed : [];
});
const columns = computed(() => columnsOf(records.value));
const rows = computed(() => records.value.map((cells) => ({ cells })));
</script>
