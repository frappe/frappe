<!-- Desk esbuild bundles do not ship frappe-ui (see ui/CLAUDE.md). Bootstrap btn
     matches existing Desk form chrome until frappe-ui is wired into desk assets. -->
<script setup>
defineProps({
	label: { type: String, default: "" },
	variant: { type: String, default: "default" },
	size: { type: String, default: "sm" },
	disabled: { type: Boolean, default: false },
});

defineEmits(["click"]);
</script>

<template>
	<button
		type="button"
		:class="['btn', `btn-${variant}`, `btn-${size}`]"
		:disabled="disabled"
		@click="$emit('click')"
	>
		<slot>{{ label }}</slot>
	</button>
</template>
