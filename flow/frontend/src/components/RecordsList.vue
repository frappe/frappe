<script setup>
import { ref, computed } from "vue";
import ArgValue from "./ArgValue.vue";
import { formatScalar, recordLabelKey, isBlockText } from "@/lib/toolMeta";
import { __ } from "@/lib/translate";

// Records laid flat: numbered, title first, every field visible right away.
const props = defineProps({ records: { type: Array, required: true } });

const ROW_LIMIT = 10;

const labelKey = computed(() => recordLabelKey(props.records));
const showAll = ref(false);

const isObj = (item) => item !== null && typeof item === "object" && !Array.isArray(item);

// One field order for every record: the union of all record keys, first seen
// first, so a field always appears in the same place regardless of per-record order.
const fieldOrder = computed(() => {
	const order = [];
	for (const rec of props.records) {
		if (!isObj(rec)) continue;
		for (const k of Object.keys(rec)) {
			if (k !== labelKey.value && !order.includes(k)) order.push(k);
		}
	}
	return order;
});

// Fields that are block text in any record render as a code block in every record,
// so a field looks the same across records regardless of one record's shorter value.
const blockKeys = computed(() => {
	const keys = new Set();
	for (const rec of props.records) {
		if (!isObj(rec)) continue;
		for (const [k, v] of Object.entries(rec)) {
			if (k !== labelKey.value && isBlockText(v)) keys.add(k);
		}
	}
	return keys;
});

const rows = computed(() => {
	const visible = showAll.value ? props.records : props.records.slice(0, ROW_LIMIT);
	return visible.map((item, i) => {
		if (!isObj(item)) return { title: formatScalar(item), rest: null };
		const rest = {};
		for (const k of fieldOrder.value) {
			if (Object.prototype.hasOwnProperty.call(item, k)) rest[k] = item[k];
		}
		const key = labelKey.value;
		const title =
			key && item[key] != null && item[key] !== ""
				? String(item[key])
				: __("Record {0}", [i + 1]);
		return { title, rest: Object.keys(rest).length ? rest : null };
	});
});
</script>

<template>
	<div class="divide-y divide-outline-gray-1">
		<div v-for="(row, i) in rows" :key="i" class="py-3 first:pt-0 last:pb-0">
			<div class="flex items-center gap-2.5" :class="{ 'mb-2.5': row.rest }">
				<span class="text-xs leading-5 tabular-nums text-ink-gray-4">{{ i + 1 }}</span>
				<span class="min-w-0 flex-1 truncate text-sm font-medium text-ink-gray-9">
					{{ row.title }}
				</span>
			</div>
			<ArgValue v-if="row.rest" :value="row.rest" :block-keys="blockKeys" />
		</div>

		<button
			v-if="records.length > ROW_LIMIT"
			class="w-full py-2 text-left text-xs text-ink-gray-5 hover:text-ink-gray-7"
			@click="showAll = !showAll"
		>
			{{ showAll ? __("Show less") : __("Show {0} more", [records.length - ROW_LIMIT]) }}
		</button>
	</div>
</template>
