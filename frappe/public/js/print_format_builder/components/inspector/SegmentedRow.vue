<template>
	<InspectorRow :label="label">
		<Segmented
			:model-value="modelValue"
			:options="options"
			@update:model-value="(v) => $emit('update:modelValue', v)"
		/>
	</InspectorRow>
</template>

<script setup>
import Segmented from "./Segmented.vue";
import InspectorRow from "./InspectorRow.vue";

defineProps({
	label: { type: String, required: true },
	modelValue: { type: [String, Number, Boolean], default: undefined },
	options: { type: Array, required: true },
});
defineEmits(["update:modelValue"]);
</script>
