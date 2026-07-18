<script setup>
// A failed tool call's error message, shown inside its dropdown.
defineProps({ message: { type: String, required: true } });
</script>

<template>
	<pre class="tool-error">{{ message }}</pre>
</template>

<style scoped>
.tool-error {
	margin: 0;
	max-height: 320px;
	overflow: auto;
	white-space: pre-wrap;
	word-break: break-word;
	border-radius: 8px;
	background: var(--surface-red-1);
	padding: 8px 10px;
	font-family: var(--font-stack-monospace, ui-monospace, monospace);
	font-size: 12.5px;
	line-height: 1.6;
	color: var(--ink-red-4);
}
</style>
