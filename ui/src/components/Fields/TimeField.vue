<template>
	<TimePicker
		v-model="value"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:error="error"
		:disabled="field.readOnly"
	>
		<template v-if="field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</TimePicker>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { TimePicker } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	// A selection is a commit for a picker: sync the value and fire the trigger.
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});
</script>
