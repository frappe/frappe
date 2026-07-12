<template>
	<div class="pfb-insp-row">
		<span class="pfb-insp-label">{{ label }}</span>
		<div ref="host"></div>
	</div>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";
import { mountColorControl } from "./useColorControl";

const props = defineProps({
	label: { type: String, required: true },
	modelValue: { type: String, default: "" },
	placeholder: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);

const host = ref(null);
let control = null;

onMounted(() => {
	control = mountColorControl(host.value, {
		value: props.modelValue || "",
		placeholder: props.placeholder || __("Default"),
		onChange(value) {
			if ((props.modelValue ?? "") !== value) emit("update:modelValue", value);
		},
	});
});

// Reflect external changes (e.g. selecting a different field) into the control
watch(
	() => props.modelValue,
	(value) => {
		if (control && (control.get_value() || "") !== (value || "")) {
			control.set_value(value || "");
		}
	}
);
</script>
