<template>
	<SliderRow
		:label="label"
		:min="min"
		:max="max"
		:model-value="parseFloat(modelValue) || fallback"
		@update:model-value="(v) => $emit('update:modelValue', v + 'px')"
	>
		<span v-if="placeholder" class="pfb-insp-hint text-muted">{{ placeholder }}</span>
	</SliderRow>
</template>

<script setup>
import SliderRow from "./SliderRow.vue";

defineProps({
	label: { type: String, required: true },
	modelValue: { type: String, default: "" },
	fallback: { type: Number, default: 200 },
	min: { type: Number, default: 20 },
	max: { type: Number, default: 700 },
	placeholder: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);
</script>
