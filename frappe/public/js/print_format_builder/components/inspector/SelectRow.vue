<template>
	<div class="pfb-insp-row">
		<span class="pfb-insp-label">{{ label }}</span>
		<Autocomplete
			class="pfb-insp-autocomplete"
			:options="options"
			:model-value="modelValue || ''"
			:placeholder="placeholder"
			@select="(o) => $emit('update:modelValue', o.value)"
		/>
	</div>
</template>

<script setup>
import Autocomplete from "../../../vue-components/Autocomplete.vue";

defineProps(["label", "modelValue", "options", "placeholder"]);
defineEmits(["update:modelValue"]);
</script>
