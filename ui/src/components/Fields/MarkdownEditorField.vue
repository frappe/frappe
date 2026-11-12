<template>
	<!-- A panel row is a plain multi-line input; CodeMirror loads only where a form draws it. -->
	<component :is="panel ? TextareaField : CodeEditorField" v-bind="props" />
</template>

<script setup lang="ts">
import { defineAsyncComponent } from "vue";
import type { FieldComponentProps } from "./types";
import TextareaField from "./TextareaField.vue";

const props = defineProps<FieldComponentProps>();

const CodeEditorField = defineAsyncComponent(() => import("./CodeEditorField.vue"));
</script>
