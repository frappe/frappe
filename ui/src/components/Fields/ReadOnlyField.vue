<template>
	<ReadValue
		:text="text"
		:label="field.label"
		:description="field.description"
		:required="field.reqd"
		:error="error"
	/>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import ReadValue from "./ReadValue.vue";
import { DocKey, ParentDocKey } from "./types";
import { NUMBER_FIELDTYPES } from "../FormLayout/formatNumber";
import { useFieldDisplay } from "../FormLayout/useFieldDisplay";
import type { FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();

const doc = inject(DocKey, null);
const parentDoc = inject(ParentDocKey, null);
const display = useFieldDisplay();

const text = computed(() => {
	const { field, modelValue } = props;
	const unset = modelValue == null || modelValue === "";
	const value = unset && NUMBER_FIELDTYPES.includes(field.fieldtype) ? 0 : modelValue;
	return display(field, value, {
		doc: doc?.value,
		row: props.row,
		parentDoc: parentDoc?.value,
	});
});
</script>
