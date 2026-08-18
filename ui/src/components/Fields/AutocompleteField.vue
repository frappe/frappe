<template>
	<Combobox
		v-model="value"
		:options="options"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		:openOnClick="true"
	/>
</template>

<script setup lang="ts">
// frappe-ui `Combobox` over newline-joined `field.options`. Combobox emits only
// `update:modelValue`; a selection is a commit, so we re-emit `change` too.
import { computed } from "vue";
import { Combobox } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});

/** Frappe `Autocomplete` options are a newline-joined string in meta. */
const options = computed(() =>
	(props.field.options ?? "")
		.split("\n")
		.map((o) => o.trim())
		.filter(Boolean)
		.map((o) => ({ label: o, value: o }))
);
</script>
