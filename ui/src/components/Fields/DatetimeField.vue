<template>
	<DateTimePicker
		v-model="value"
		:format="formats.datetime"
		v-model:open="open"
		v-bind="frame"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
	/>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { DateTimePicker } from "frappe-ui";
import { dateTimeFormats } from "../FormLayout/formatDefaults";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import { descriptionText } from "./fieldDescription";
import { usePickerFrame } from "./inputFrame";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
const frame = usePickerFrame(props, { describe: descriptionText });
const open = ref(!!props.openPicker);

const formats = computed(dateTimeFormats);

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	// A selection is a commit for a picker: sync the value and fire the trigger.
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});
</script>
