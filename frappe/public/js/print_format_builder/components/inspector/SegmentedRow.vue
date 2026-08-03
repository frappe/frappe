<template>
	<div class="pfb-insp-row">
		<span class="pfb-insp-label">{{ label }}</span>
		<Segmented
			:model-value="modelValue"
			:options="options"
			@update:model-value="(v) => $emit('update:modelValue', v)"
		/>
	</div>
</template>

<script setup>
import Segmented from "./Segmented.vue";

defineProps({
	label: { type: String, required: true },
	modelValue: { type: [String, Number, Boolean], default: undefined },
	options: { type: Array, required: true },
});
defineEmits(["update:modelValue"]);
</script>
