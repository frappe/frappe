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
// names a *sibling field* (`field.options`) whose value on the doc holds the
// doctype to link into (Frappe's Dynamic Link convention; CRM resolves the same
// way via `data[field.options]`). We read it from the injected doc; until that
// sibling has a value there's nothing to search, so the control disables.
import { computed, inject } from "vue";
import { Link } from "../../Link";
import { DocKey } from "../types";
import type { FieldComponentEmits, FieldComponentProps } from "../types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const doc = inject(DocKey, null);

const doctype = computed<string>(() => {
	const sibling = props.field.options;
	const dt = sibling ? doc?.value?.[sibling] : null;
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
