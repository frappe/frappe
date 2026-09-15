<template>
	<div class="pfb-insp-row">
		<span class="pfb-insp-label">{{ label }}</span>
		<select
			class="pfb-insp-select"
			:value="modelValue || ''"
			@change="$emit('update:modelValue', $event.target.value)"
		>
			<option value="">{{ placeholder }}</option>
			<option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
		</select>
	</div>
</template>

<script setup>
defineProps(["label", "modelValue", "options", "placeholder"]);
defineEmits(["update:modelValue"]);
</script>
