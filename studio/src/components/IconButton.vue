<template>
	<Tooltip :disabled="!label" :placement="tooltipPlacement" :text="label" :hover-delay="hoverDelay">
		<button class="flex gap-2 text-sm text-ink-gray-5 hover:text-ink-gray-8" v-bind="attrs" ref="rootRef">
			<component :is="icon" :class="iconClasses" />
		</button>
	</Tooltip>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui"
import { computed, useAttrs, ref, type Component } from "vue"

const props = withDefaults(
	defineProps<{
		icon: Component
		label?: string
		size?: "sm" | "md" | "lg"
		hoverDelay?: number
		tooltipPlacement?: "top" | "right" | "bottom" | "left"
	}>(),
	{
		size: "md",
		hoverDelay: 0.1,
		tooltipPlacement: "right",
	},
)
const attrs = useAttrs()

const rootRef = ref<HTMLElement | null>(null)
defineExpose({ rootRef })

const iconClasses = computed(() => {
	return {
		sm: "h-3 w-3",
		md: "h-4 w-4",
		lg: "h-5 w-5",
	}[props.size]
})
</script>
