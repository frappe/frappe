<template>
	<Link
		v-model="value"
		:doctype="doctype"
		:filters="field.filters"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly || !doctype"
	/>
</template>

<script setup lang="ts">
// Dynamic Link: the target doctype is named by a sibling field (`field.options`),
// resolved via `pickSiblingValue` (row → doc → parent). Disabled until it has a value.
import { computed, inject } from "vue";
import { Link } from "../Link";
import { DocKey, ParentDocKey } from "./types";
import { pickSiblingValue } from "../FormLayout/pickSiblingValue";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const doc = inject(DocKey, null);
const parentDoc = inject(ParentDocKey, null);

const doctype = computed<string>(() => {
	const sibling = props.field.options;
	const dt = sibling
		? pickSiblingValue(
				{ row: props.row, doc: doc?.value, parentDoc: parentDoc?.value },
				sibling
		  )
		: null;
	return typeof dt === "string" ? dt : "";
});

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});
</script>
