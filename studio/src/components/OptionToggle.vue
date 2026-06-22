<!-- Extracted from Builder -->
<template>
	<div class="flex w-full items-center justify-between">
		<InputLabel v-if="label">{{ label }}</InputLabel>
		<TabButtons
			class="w-full min-w-[150px] [&>div]:flex [&>div]:w-full [&_[data-slot=tab-button]>*]:w-full [&_[data-slot=tab-button]]:flex-1"
			:buttons="options"
			:modelValue="modelValue"
			@update:modelValue="$emit('update:modelValue', $event)"
		></TabButtons>
	</div>
</template>
<script setup lang="ts">
import InputLabel from "@/components/InputLabel.vue"
import { TabButtons, ButtonProps } from "frappe-ui"

type ButtonProps = typeof ButtonProps
defineProps({
	modelValue: {
		type: [String, Number, Boolean],
	},
	options: {
		type: Array<ButtonProps>,
		default: () => [],
	},
	label: {
		type: String,
		default: "",
	},
})

const emit = defineEmits(["update:modelValue"])
</script>
