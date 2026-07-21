<template>
	<button
		type="button"
		class="pfb-insp-toggle"
		:class="{ active: modelValue }"
		:aria-pressed="!!modelValue"
		:title="title"
		@click="$emit('update:modelValue', !modelValue)"
		v-html="frappe.utils.icon(icon, 'sm')"
	></button>
</template>

<script setup>
defineProps({
	modelValue: { type: Boolean, default: false },
	icon: { type: String, required: true },
	title: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);
</script>

<style scoped>
.pfb-insp-toggle {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	align-self: stretch;
	width: 32px;
	flex-shrink: 0;
	padding: 0;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--control-bg);
	color: var(--text-muted);
	cursor: pointer;
}
.pfb-insp-toggle:hover {
	background: var(--gray-200);
	color: var(--text-color);
}
.pfb-insp-toggle.active {
	background: var(--gray-300);
	border-color: var(--gray-400);
	color: var(--text-color);
}
</style>
