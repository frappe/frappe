<template>
	<InspectorRow :label="label" toggle>
		<Switch
			:label="label"
			:model-value="modelValue"
			@update:model-value="(v) => $emit('update:modelValue', v)"
		/>
	</InspectorRow>
</template>

<script setup>
import InspectorRow from "./InspectorRow.vue";
import Switch from "./Switch.vue";

defineProps({
	label: { type: String, default: "" },
	modelValue: { type: Boolean, default: false },
});
defineEmits(["update:modelValue"]);
</script>
