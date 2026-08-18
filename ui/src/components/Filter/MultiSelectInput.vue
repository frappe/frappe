<!--
  The `in` / `not in` value input for an option field (Select / Autocomplete): a
  frappe-ui MultiSelect over the field's own newline-joined meta options, so the
  user picks exact values instead of typing an error-prone comma string. Its
  `v-model` is the condition's value — a `string[]` of the chosen option values.
-->
<template>
	<MultiSelect
		:modelValue="selected"
		:options="options"
		:placeholder="placeholder ?? 'Select options'"
		variant="subtle"
		@update:modelValue="(v) => emit('update:modelValue', v)"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { MultiSelect } from "frappe-ui";
import type { FilterField } from "./types";

const props = defineProps<{
	field: FilterField;
	modelValue: string[];
	placeholder?: string;
}>();

const emit = defineEmits<{ "update:modelValue": [value: string[]] }>();

// Tolerate a stray scalar (e.g. a value left over from a prior operator) — the
// MultiSelect only ever speaks `string[]`.
const selected = computed<string[]>(() =>
	Array.isArray(props.modelValue) ? props.modelValue : []
);

/** Frappe `Select` / `Autocomplete` options are a newline-joined string in meta. */
const options = computed(() =>
	(props.field.options ?? "")
		.split("\n")
		.map((o) => o.trim())
		.filter(Boolean)
		.map((o) => ({ label: o, value: o }))
);
</script>
