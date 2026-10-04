<template>
	<InspectorRow :label="label" :stacked="stacked">
		<select
			class="pfb-insp-select"
			:value="modelValue ?? ''"
			@change="$emit('update:modelValue', $event.target.value)"
		>
			<option v-if="placeholder" value="" disabled hidden>{{ placeholder }}</option>
			<option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
		</select>
	</InspectorRow>
</template>

<script setup>
import InspectorRow from "./InspectorRow.vue";

defineProps({
	label: { type: String, required: true },
	modelValue: { type: [String, Number], default: "" },
	options: { type: Array, required: true },
	placeholder: { type: String, default: "" },
	stacked: { type: Boolean, default: false },
});
defineEmits(["update:modelValue"]);
</script>
