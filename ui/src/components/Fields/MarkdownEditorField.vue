<template>
	<component
		:is="panel ? TextareaField : CodeEditorField"
		v-bind="props"
		@update:modelValue="emit('update:modelValue', $event)"
		@change="emit('change', $event)"
	/>
</template>

<script setup lang="ts">
import { defineAsyncComponent } from "vue";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import TextareaField from "./TextareaField.vue";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// A panel row is a plain multi-line input; CodeMirror loads only where a form draws it.
const CodeEditorField = defineAsyncComponent(() => import("./CodeEditorField.vue"));
</script>
