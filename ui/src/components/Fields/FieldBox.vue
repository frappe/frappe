<!-- The box every panel row draws in, at rest and open: the hover and focus looks live here.
     An open popover holds the focus in its portal, so `data-state=open` keeps the focus look. -->
<template>
	<div
		class="field-box min-h-7 w-full min-w-0 rounded-4 focus-within:bg-surface-gray-2 focus-within:ring-1 focus-within:ring-inset has-[[data-state=open]]:bg-surface-gray-2 has-[[data-state=open]]:ring-1 has-[[data-state=open]]:ring-inset"
		:class="[
			interactive ? 'hover:bg-surface-gray-2' : '',
			error
				? 'focus-within:ring-outline-red-3 has-[[data-state=open]]:ring-outline-red-3'
				: 'focus-within:ring-outline-gray-3 has-[[data-state=open]]:ring-outline-gray-3',
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
/* The box ring is the only focus mark: hide a control's own outline (kept transparent for forced colors) and the forms plugin's ring, not a row button's. */
.field-box :deep(:focus-visible:not(button, a, [role="button"])),
.field-box :deep(:is(input, textarea, select):focus) {
	outline: 2px solid transparent;
	box-shadow: none;
}
/* frappe-ui's textarea size classes (`py-1.5`, `min-h-9`, `text-p-sm`) are one class deep: a scoped
   attribute selector outweighs them without `!important`. */
.field-box :deep(textarea[data-slot="control"]) {
	@apply max-h-32 min-h-7 resize-none overflow-y-auto px-2 py-1 text-base leading-5;
}
.field-box[data-error] :deep([data-slot="control"]) {
	color: var(--ink-red-6);
}
</style>
