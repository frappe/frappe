<template>
	<div class="pfb-style-body">
		<textarea
			class="pfb-insp-input pfb-style-input"
			rows="4"
			spellcheck="false"
			:placeholder="'border: 1px solid #e5e7eb;\npadding: 6px;'"
			:value="modelValue"
			@input="$emit('update:modelValue', $event.target.value)"
		></textarea>
		<p class="pfb-insp-hint text-muted">
			{{ __("CSS declarations applied inline, e.g.") }} <code>color: #1a5fb4;</code>
		</p>
	</div>
</template>

<script setup>
defineProps(["modelValue"]);
defineEmits(["update:modelValue"]);
</script>

<style scoped>
.pfb-style-body {
	display: flex;
	flex-direction: column;
	gap: 6px;
	padding: 4px 14px 12px;
}

.pfb-style-input {
	width: 100%;
	font-family: var(--monospace-font-family, monospace);
	font-size: var(--text-sm);
	line-height: 1.5;
	resize: vertical;
	min-height: 60px;
}
</style>
