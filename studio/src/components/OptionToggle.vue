<!-- Extracted from Builder -->
<template>
	<div class="flex w-full items-center justify-between">
		<InputLabel v-if="label">{{ label }}</InputLabel>
		<TabButtons
			class="w-full min-w-[150px] [&>div>div>button]:w-full [&>div>div]:flex [&>div>div]:flex-1"
			:buttons="options"
			:modelValue="modelValue"
			@update:modelValue="$emit('update:modelValue', $event)"
		></TabButtons>
	</div>
</template>
<script setup lang="ts">
import InputLabel from "@/components/InputLabel.vue"
import { TabButtons } from "frappe-ui"
import { PropType } from "vue"

defineProps({
	modelValue: {
		type: [String, Number, Boolean],
	},
	options: {
		type: Array as PropType<{ label: string; value?: string | number; icon?: string; hideLabel?: boolean }[]>,
		default: () => [],
	},
	label: {
		type: String,
		default: "",
	},
})

const emit = defineEmits(["update:modelValue"])
</script>
