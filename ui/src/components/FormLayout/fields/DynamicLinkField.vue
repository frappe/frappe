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
// Like `LinkField`, but the target doctype is not a constant on the field — it
// names a *sibling field* (`field.options`) whose value holds the doctype to
// link into (Frappe's Dynamic Link convention; CRM resolves the same way via
// `data[field.options]`). We resolve that sibling across the same records a
// Currency field does — the row's own column, then the field's doc, then the
// parent doc (`pickSiblingValue`) — so a Dynamic Link in a child row reads its
// controlling field from the *row* and stays in sync between the grid cell and
// the row dialog. Until that sibling has a value there's nothing to search, so
// the control disables.
import { computed, inject } from "vue";
import { Link } from "../../Link";
import { DocKey, ParentDocKey } from "../types";
import { pickSiblingValue } from "../pickSiblingValue";
import type { FieldComponentEmits, FieldComponentProps } from "../types";

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
