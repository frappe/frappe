<template>
	<button
		type="button"
		class="pfb-insp-toggle"
		:class="{ active: modelValue }"
		:aria-pressed="!!modelValue"
		:title="title"
		@click="$emit('update:modelValue', !modelValue)"
	>
		{{ label }}
	</button>
</template>

<script setup>
defineProps({
	modelValue: { type: Boolean, default: false },
	label: { type: String, required: true },
	title: { type: String, default: "" },
});
defineEmits(["update:modelValue"]);
</script>

<style scoped>
/* No border or fill at rest: the row it sits on supplies the context, and a
   resting outline is what made these read as permanently pressed. */
.pfb-insp-toggle {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 26px;
	height: 26px;
	flex-shrink: 0;
	padding: 0;
	border: none;
	border-radius: var(--radius);
	background: transparent;
	color: var(--text-muted);
	font-size: var(--text-md);
	font-weight: 700;
	line-height: 1;
	cursor: pointer;
}
.pfb-insp-toggle:hover {
	background: var(--gray-100);
	color: var(--text-color);
}
.pfb-insp-toggle.active {
	background: var(--text-color);
	color: var(--fg-color);
}
</style>
