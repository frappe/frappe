<template>
	<InspectorRow :label="label" :stacked="stacked">
		<input
			type="text"
			class="pfb-insp-input"
			:placeholder="placeholder"
			:value="modelValue ?? ''"
			@change="$emit('update:modelValue', $event.target.value)"
		/>
		<slot />
	</InspectorRow>
</template>

<script setup>
import InspectorRow from "./InspectorRow.vue";

defineProps({
	label: { type: String, required: true },
	modelValue: { type: String, default: "" },
	placeholder: { type: String, default: "" },
	stacked: { type: Boolean, default: false },
});
defineEmits(["update:modelValue"]);
</script>
