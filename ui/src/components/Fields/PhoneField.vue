<template>
	<TextInput
		type="tel"
		:modelValue="modelValue"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		@update:modelValue="(value: any) => emit('update:modelValue', value)"
		@change="(e: Event) => emit('change', (e.target as HTMLInputElement).value)"
	/>
</template>

<script setup lang="ts">
// Minimal `type=tel` text box; value is the raw string. Core's `controls/phone.js`
// adds an ISD picker and stores a composite `"ISD-number"` — a later upgrade.
import { TextInput } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
</script>
