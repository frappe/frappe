<template>
	<div class="pfb-insp-row">
		<span class="pfb-insp-label">{{ label }}</span>
		<div class="pfb-insp-color">
			<div ref="host" class="pfb-insp-color-input"></div>
			<slot />
		</div>
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
/* only_input wraps the colour input in a .form-group with a 1rem bottom margin,
   which unbalances the row's vertical centering against the label */
.pfb-insp-row :deep(.form-group) {
	margin-bottom: 0;
}
.pfb-insp-color {
	display: flex;
	align-items: center;
	gap: 4px;
}
.pfb-insp-color-input {
	flex: 1;
	min-width: 0;
}
</style>
