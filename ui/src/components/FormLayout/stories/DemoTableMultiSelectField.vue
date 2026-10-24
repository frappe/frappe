<!--
  An app's own `Table MultiSelect` field, registered over the lib's: it turns on `creatable`
  and, in place of a create dialog, selects the typed text.
-->
<template>
	<TableMultiSelect
		v-model="value"
		:doctype="targetDoctype"
		:filters="field.filters"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		creatable
		@create="onCreate"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { TableMultiSelect } from "../../TableMultiSelect";
import { useChildRowModel } from "../useChildRowModel";
import { newRowValues } from "../newRowValues";
import type { FieldComponentProps, FieldComponentEmits } from "../types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const linkField = computed(() => props.field.childFields?.find((f) => f.fieldtype === "Link"));
const targetDoctype = computed(() => linkField.value?.options ?? "");

const value = useChildRowModel(
	() => props.modelValue,
	() => linkField.value?.fieldname ?? "",
	emit,
	// No `parentfield`: this demo has never signalled row changes (a story has no
	// commit channel to signal onto). The seed is what it shares with the lib field.
	undefined,
	() => newRowValues(props.field.childFields ?? [])
);

function onCreate(query: string) {
	console.log("create", { doctype: targetDoctype.value, query });
	// Prove the round-trip: pretend the record was created and select it.
	if (query && !value.value.includes(query)) value.value = [...value.value, query];
}
</script>
