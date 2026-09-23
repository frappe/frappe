<template>
	<div ref="host" class="pfb-insp-color-input"></div>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";
import { mountColorControl } from "./useColorControl";

const props = defineProps({
	modelValue: { type: String, default: "" },
	placeholder: { type: String, default: "" },
	fieldname: { type: String, default: "color" },
});
const emit = defineEmits(["update:modelValue"]);

const host = ref(null);
let control = null;

onMounted(() => {
	control = mountColorControl(host.value, {
		value: props.modelValue || "",
		placeholder: props.placeholder || __("Default"),
		fieldname: props.fieldname,
		onChange(value) {
			if ((props.modelValue ?? "") !== value) emit("update:modelValue", value);
		},
	});
});

watch(
	() => props.modelValue,
	(value) => {
		if (control && (control.get_value() || "") !== (value || "")) {
			control.set_value(value || "");
		}
	}
);
</script>

<style scoped>
.pfb-insp-color-input {
	flex: 1;
	min-width: 0;
}
.pfb-insp-color-input :deep(.form-group) {
	margin-bottom: 0;
}
</style>
