<template>
	<button
		class="es-button"
		data-size="xs"
		data-variant="ghost"
		data-theme="red"
		data-icon-button="true"
		:title="__('Remove section')"
		@click.stop="$emit('remove')"
		v-html="frappe.utils.icon('x', size)"
	></button>
</template>

<script setup>
import { inject } from "vue";

defineProps({
	section: { type: Object, required: true },
	size: { type: String, default: "sm" },
});
defineEmits(["remove"]);

const store = inject("$store");
</script>
