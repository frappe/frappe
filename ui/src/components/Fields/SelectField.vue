<template>
	<Select
		v-model="value"
		v-model:open="open"
		:options="options"
		v-bind="frame"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
	>
		<template v-if="panel" #footer><PickerListFit /></template>
		<template v-if="!panel && field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</Select>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Select } from "frappe-ui";
import { fieldChoices } from "./choices";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";
import PickerListFit from "./PickerListFit.vue";
import { usePickerFrame } from "./inputFrame";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
const frame = usePickerFrame(props);
const open = ref(!!props.openPicker);

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	// A selection is a commit for a picker: sync the value and fire the trigger.
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});

/** Frappe `Select` options are a newline-joined string in meta; a script may set labelled pairs. */
const options = computed(() => fieldChoices(props.field));
</script>
