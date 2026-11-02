<script setup>
import { computed } from "vue";
import { useDoctypeMeta } from "@framework/ui";
import { Filter, getFilterableFields, parseFilters, serializeFilters } from "@framework/ui/Filter";

// The shared Filter speaks [field, operator, value]; desk stores [doctype, field, operator, value] rows.
const props = defineProps({
	doctype: { type: String, required: true },
	filters: { type: Array, default: null },
	compact: { type: Boolean, default: false },
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
			])
		),
});
</script>

<template>
	<Filter v-model="model" :doctype="doctype" :compact="compact" />
</template>
