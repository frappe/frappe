<!--
  Demo of the host-side override pattern for `Table MultiSelect`: a field that
  turns on the control's `creatable` affordance and wires `@create` to app
  behaviour. The lib ships a plain select-only `TableMultiSelectField`; an app
  that wants "Create '{query}'" registers its own component via
  `registerFieldType('Table MultiSelect', …)` — no lib changes, no prop on
  FormLayout. Mirrors `DemoLinkField`, and stays thin because the search +
  trigger + footer all live in the shared `TableMultiSelect` control. Here the
  handler just `console.log`s and optimistically selects the typed value; a real
  host would open a quick-entry dialog and select the inserted record's name.
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
import type { FieldComponentProps, FieldComponentEmits } from "../types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const linkField = computed(() => props.field.childFields?.find((f) => f.fieldtype === "Link"));
const targetDoctype = computed(() => linkField.value?.options ?? "");

const value = useChildRowModel(
	() => props.modelValue,
	() => linkField.value?.fieldname ?? "",
	emit
);

function onCreate(query: string) {
	console.log("create", { doctype: targetDoctype.value, query });
	// Prove the round-trip: pretend the record was created and select it.
	if (!value.value.includes(query)) value.value = [...value.value, query];
}
</script>
