<template>
	<button
		type="button"
		class="pfb-insp-toggle"
		:class="{ active: modelValue }"
		:aria-pressed="!!modelValue"
		:title="title"
		@click="$emit('update:modelValue', !modelValue)"
	>
		<span v-if="icon" v-html="frappe.utils.icon(icon, 'sm')"></span>
		<template v-else>{{ label }}</template>
	</button>
</template>

<script setup>
defineProps({
	modelValue: { type: Boolean, default: false },
	label: { type: String, default: "" },
	icon: { type: String, default: "" },
	title: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);
</script>

<style scoped>
.pfb-insp-toggle {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	min-width: 32px;
	padding: 5px 10px;
	font-size: var(--text-sm);
	line-height: 1;
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
	font-weight: var(--weight-medium);
}
</style>
