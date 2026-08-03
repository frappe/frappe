<template>
	<div class="pfb-seg">
		<button
			v-for="opt in options"
			:key="opt.value"
			type="button"
			:class="{ active: modelValue === opt.value }"
			:title="opt.title || null"
			@click="$emit('update:modelValue', opt.value)"
		>
			<span v-if="opt.icon" v-html="opt.icon"></span>
			<template v-else>{{ opt.label }}</template>
		</button>
	</div>
</template>

<script setup>
defineProps({
	modelValue: { type: [String, Number, Boolean], default: undefined },
	options: { type: Array, required: true },
});
defineEmits(["update:modelValue"]);
</script>

<style scoped>
.pfb-seg {
	display: inline-flex;
	background: var(--control-bg);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	overflow: hidden;
	width: 100%;
}
.pfb-seg button {
	flex: 1;
	padding: 5px 6px;
	font-size: var(--text-tiny);
	font-weight: var(--weight-medium);
	border: none;
	border-radius: 0;
	background: transparent;
	color: var(--text-muted);
	cursor: pointer;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	line-height: 1;
}
.pfb-seg button:not(:first-child) {
	border-left: 1px solid var(--border-color);
}
.pfb-seg button:hover {
	background: var(--gray-200);
	color: var(--text-color);
}
.pfb-seg button.active {
	background: var(--fg-color);
	color: var(--text-color);
	box-shadow: var(--shadow-xs);
}
</style>
