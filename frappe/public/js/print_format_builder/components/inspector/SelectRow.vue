<template>
	<InspectorRow :label="label">
		<Autocomplete
			class="pfb-insp-autocomplete"
			:options="options"
			:model-value="modelValue || ''"
			:placeholder="placeholder"
			@select="(o) => $emit('update:modelValue', o.value)"
		/>
	</InspectorRow>
</template>

<script setup>
import Autocomplete from "../../../vue-components/Autocomplete.vue";
import InspectorRow from "./InspectorRow.vue";

defineProps({
	label: { type: String, required: true },
	modelValue: { type: String, default: "" },
	options: { type: Array, required: true },
	placeholder: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);
</script>
