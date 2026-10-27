<!-- A field the user cannot edit, drawn as its formatted value (see `readView.ts` for which fields). -->
<template>
	<ReadValue
		:text="text"
		:label="field.label"
		:description="field.description"
		:required="field.reqd"
		:error="error"
	/>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import ReadValue from "./ReadValue.vue";
import { DocKey } from "./types";
import { useFieldDisplay } from "../FormLayout/useFieldDisplay";
import type { FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();

const doc = inject(DocKey, null);
const display = useFieldDisplay();

// A grid cell passes its row; a form field reads the document.
const text = computed(() => {
	const record = props.row ?? doc?.value ?? {};
	return display(props.field, { ...record, [props.field.fieldname]: props.modelValue });
});
</script>
