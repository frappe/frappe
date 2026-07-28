<template>
	<button
		class="es-button"
		data-size="xs"
		data-variant="ghost"
		data-icon-button="true"
		:title="__('Copy section')"
		@click.stop="store.copy_section(section)"
		v-html="frappe.utils.icon('copy', size)"
	></button>
	<button
		class="es-button"
		data-size="xs"
		data-variant="ghost"
		data-icon-button="true"
		:title="__('Duplicate section')"
		@click.stop="store.duplicate_section(section)"
		v-html="frappe.utils.icon('copy-plus', size)"
	></button>
	<button
		class="es-button"
		data-size="xs"
		data-variant="ghost"
		data-icon-button="true"
		:title="__('Save as snippet')"
		@click.stop="$emit('snippet')"
		v-html="frappe.utils.icon('bookmark-plus', size)"
	></button>
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
defineEmits(["snippet", "remove"]);

const store = inject("$store");
</script>
