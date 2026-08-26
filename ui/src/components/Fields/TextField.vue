<template>
	<TextInput
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
import { TextInput } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
</script>
