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
	/>
</template>

<script setup lang="ts">
// `Table MultiSelect` → the reusable `TableMultiSelect` control. In Frappe this
// fieldtype is backed by a child table whose single `Link` field names the real
// target doctype; the stored value is an array of child rows. We resolve that
// link field from `childFields` (populated by buildLayoutFromMeta) and bridge
// the row array to the control's `string[]` via `useChildRowModel`.
//
// Select-only, like `LinkField`. An app wanting `creatable` (or any extra
// behaviour) registers its own field that renders `<TableMultiSelect creatable
// @create>` — see stories/DemoTableMultiSelectField.vue.
import { computed } from "vue";
import { TableMultiSelect } from "../../TableMultiSelect";
import { useChildRowModel } from "../useChildRowModel";
import type { FieldComponentEmits, FieldComponentProps } from "../types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// The child table's single Link field: its `options` is the target doctype to
// search, its `fieldname` is the key each stored row holds the value under.
const linkField = computed(() => props.field.childFields?.find((f) => f.fieldtype === "Link"));
const targetDoctype = computed(() => linkField.value?.options ?? "");

const value = useChildRowModel(
	() => props.modelValue,
	() => linkField.value?.fieldname ?? "",
	emit
);
</script>
