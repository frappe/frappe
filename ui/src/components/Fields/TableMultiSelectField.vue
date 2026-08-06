<template>
	<TableMultiSelect
		v-model="value"
		:doctype="targetDoctype"
		:filters="field.filters"
		:label="field.label"
		:description="
			targetDoctype
				? field.description
				: 'Child table metadata unavailable — picker disabled.'
		"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly || !targetDoctype"
	/>
</template>

<script setup lang="ts">
// Frappe `Table MultiSelect`: a child table whose single Link field names the
// target doctype; stored value is an array of child rows, bridged to the
// control's `string[]` via `useChildRowModel`. Select-only, like `LinkField`.
import { computed } from "vue";
import { TableMultiSelect } from "../TableMultiSelect";
import { useChildRowModel } from "../FormLayout/useChildRowModel";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// Link field's `options` is the target doctype; its `fieldname` is the key each row stores the value under.
const linkField = computed(() => props.field.childFields?.find((f) => f.fieldtype === "Link"));
const targetDoctype = computed(() => linkField.value?.options ?? "");

const value = useChildRowModel(
	() => props.modelValue,
	() => linkField.value?.fieldname ?? "",
	emit
);
</script>
