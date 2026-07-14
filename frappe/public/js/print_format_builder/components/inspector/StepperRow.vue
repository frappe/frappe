<template>
	<div class="pfb-insp-row">
		<span class="pfb-insp-label">{{ label }}</span>
		<Stepper
			:sm="sm"
			:value="modelValue ?? ''"
			:placeholder="placeholder"
			:unit="unit"
			@decrement="adjust(-step)"
			@increment="adjust(step)"
			@input="on_input"
		/>
	</div>
</template>

<script setup>
import Stepper from "./Stepper.vue";

const props = defineProps({
	label: { type: String, required: true },
	modelValue: { type: Number, default: null },
	step: { type: Number, default: 1 },
	base: { type: Number, default: 0 },
	min: { type: Number, default: 0 },
	unit: { type: String, default: "" },
	placeholder: { type: String, default: "" },
	allowEmpty: { type: Boolean, default: false },
	sm: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue"]);

function adjust(delta) {
	const current = props.modelValue ?? props.base;
	emit("update:modelValue", Math.max(props.min, current + delta));
}

function on_input(v) {
	const n = parseInt(v);
	if (isNaN(n)) {
		emit("update:modelValue", props.allowEmpty ? null : 0);
		return;
	}
	emit("update:modelValue", Math.max(props.min, n));
}
</script>
