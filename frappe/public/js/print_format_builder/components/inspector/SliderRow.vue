<template>
	<InspectorRow :label="label" stacked>
		<input
			class="pfb-size-slider"
			type="range"
			:min="min"
			:max="max"
			:value="modelValue"
			@input="$emit('update:modelValue', Number($event.target.value))"
		/>
		<slot />
	</InspectorRow>
</template>

<script setup>
import InspectorRow from "./InspectorRow.vue";

defineProps({
	label: { type: String, required: true },
	modelValue: { type: Number, default: 0 },
	min: { type: Number, default: 20 },
	max: { type: Number, default: 700 },
});
defineEmits(["update:modelValue"]);
</script>
