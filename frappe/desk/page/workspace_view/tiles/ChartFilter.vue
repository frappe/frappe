<script setup>
import { computed } from "vue";
import { useDoctypeMeta } from "@framework/ui";
import { Filter, getFilterableFields, parseFilters, serializeFilters } from "@framework/ui/Filter";

// The shared Filter speaks [field, operator, value]; a chart stores desk's filter rows.
const props = defineProps({
	doctype: { type: String, required: true },
	filters: { type: Array, default: null },
});

const emit = defineEmits(["change"]);

const { meta } = useDoctypeMeta(props.doctype);
const fields = computed(() => getFilterableFields(meta.value?.fields ?? [], props.doctype));

const model = computed({
	get: () =>
		parseFilters(
			fields.value,
			(props.filters || []).map(([, field, operator, value]) => [field, operator, value])
		),
	set: (conditions) =>
		emit(
			"change",
			serializeFilters(conditions).map(([field, operator, value]) => [
				props.doctype,
				field,
				operator,
				value,
				false,
			])
		),
});
</script>

<template>
	<Filter v-model="model" :doctype="doctype" />
</template>
