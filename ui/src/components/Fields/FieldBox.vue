<!-- The box every panel row draws in, at rest and open: the hover and focus looks live here. -->
<template>
	<div
		class="field-box min-h-7 w-full min-w-0 rounded-4 focus-within:bg-surface-gray-2 focus-within:ring-1 focus-within:ring-inset"
		:class="[
			interactive ? 'hover:bg-surface-gray-2' : '',
			error ? 'focus-within:ring-outline-red-3' : 'focus-within:ring-outline-gray-3',
		]"
		:data-error="error || undefined"
	>
		<slot />
	</div>
</template>

<script setup lang="ts">
defineProps<{
	error?: boolean;
	/** Whether the box takes the hover fill: an editable or summary row. */
	interactive?: boolean;
}>();
</script>

<style scoped>
/* Ghost controls keep frappe-ui's own transition and placeholder colour; the box owns both. */
.field-box :deep([data-slot="control"]) {
	transition: none;
}
.field-box :deep([data-slot="control"])::placeholder {
	color: var(--ink-gray-4);
}
/* Chrome draws a password input's dots 1px above the same dots in text: pad the top to match. */
.field-box :deep(input[data-slot="control"][type="password"]) {
	padding-top: 8px;
}
.field-box[data-error] :deep([data-slot="control"]) {
	color: var(--ink-red-4);
}
</style>
