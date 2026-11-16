<template>
	<DatePicker
		:id="pickerId"
		:key="externalKey"
		v-model="value"
		:format="formats.date"
		v-model:open="open"
		v-bind="frame"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
	/>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { DatePicker } from "frappe-ui";
import { dateTimeFormats } from "../FormLayout/formatDefaults";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import { descriptionText } from "./fieldDescription";
import { usePickerFrame } from "./inputFrame";
import { usePickerExternalValue } from "./pickerExternalValue";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
const frame = usePickerFrame(props, { describe: descriptionText });
const open = ref(!!props.openPicker);
const {
	id: pickerId,
	key: externalKey,
	accept,
} = usePickerExternalValue(() => props.modelValue, open);

const formats = computed(dateTimeFormats);

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	// A selection is a commit for a picker: sync the value and fire the trigger.
	set: (v) => {
		if (!accept(v)) return;
		emit("update:modelValue", v);
		emit("change", v);
	},
});
</script>
