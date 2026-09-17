<template>
	<div class="pfb-insp-row pfb-insp-row--col">
		<span class="pfb-insp-label">{{ label }}</span>
		<input
			class="pfb-size-slider"
			type="range"
			:min="min"
			:max="max"
			:value="modelValue"
			@input="$emit('update:modelValue', Number($event.target.value))"
		/>
	</div>
</template>

<script setup>
defineProps({
	label: { type: String, required: true },
	modelValue: { type: Number, default: 0 },
	min: { type: Number, default: 20 },
	max: { type: Number, default: 700 },
});
defineEmits(["update:modelValue"]);
</script>
