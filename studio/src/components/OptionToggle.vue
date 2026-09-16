<!-- Extracted from Builder -->
<template>
	<div class="flex w-full items-center justify-between">
		<InputLabel v-if="label">{{ label }}</InputLabel>
		<TabButtons
			class="w-full min-w-[150px]"
			fluid
			:options="options"
			:modelValue="modelValue"
			@update:modelValue="$emit('update:modelValue', $event)"
		></TabButtons>
	</div>
</template>
<script setup lang="ts">
import type { PropType } from "vue"
import InputLabel from "@/components/InputLabel.vue"
import { TabButtons, type TabButton } from "frappe-ui"

defineProps({
	modelValue: {
		type: [String, Number],
	},
	options: {
		type: Array as PropType<TabButton[]>,
		default: () => [],
	},
	label: {
		type: String,
		default: "",
	},
})

const emit = defineEmits(["update:modelValue"])
</script>
