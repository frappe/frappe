<template>
	<Checkbox
		v-model="value"
		:label="field.label"
		:description="field.description"
		:required="field.reqd"
		:disabled="field.readOnly"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Checkbox } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// The doc holds `0 | 1`, as the server stores it; the checkbox speaks boolean.
const value = computed<boolean>({
	get: () => Boolean(props.modelValue),
	// Toggling a checkbox is a commit: sync the value and fire the trigger.
	set: (v) => {
		const checked = v ? 1 : 0;
		emit("update:modelValue", checked);
		emit("change", checked);
	},
});
</script>
