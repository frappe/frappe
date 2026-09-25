<template>
	<Textarea
		v-model="value"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		@change="(e: Event) => emit('change', (e.target as HTMLTextAreaElement).value)"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Textarea } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	set: (v) => emit("update:modelValue", v),
});
</script>
