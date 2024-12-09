<template>
	<Tooltip :disabled="!label" placement="right" :text="label" :hover-delay="hoverDelay">
		<button class="flex gap-2 text-sm text-gray-600 hover:text-gray-900" v-bind="attrs">
			<FeatherIcon :name="icon" :class="iconClasses" />
		</button>
	</Tooltip>
</template>

<script setup lang="ts">
import { FeatherIcon, Tooltip } from "frappe-ui"
import { computed, useAttrs } from "vue"

const props = withDefaults(
	defineProps<{
		icon: string
		label?: string
		size?: "sm" | "md" | "lg"
		hoverDelay?: number
	}>(),
	{
		size: "md",
		hoverDelay: 0.1,
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
