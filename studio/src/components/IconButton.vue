<template>
	<Tooltip :disabled="!label" :placement="tooltipPlacement" :text="label" :hover-delay="hoverDelay">
		<button class="flex gap-2 text-sm text-gray-600 hover:text-gray-900" v-bind="attrs">
			<FeatherIcon v-if="typeof icon === 'string'" :name="icon" :class="iconClasses" />
			<component v-else :is="icon" :class="iconClasses" />
		</button>
	</Tooltip>
</template>

<script setup lang="ts">
import { FeatherIcon, Tooltip } from "frappe-ui"
import { computed, useAttrs, type Component } from "vue"

const props = withDefaults(
	defineProps<{
		icon: string | Component
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

const iconClasses = computed(() => {
	return {
		sm: "h-3 w-3",
		md: "h-4 w-4",
		lg: "h-5 w-5",
	}[props.size]
})
</script>
