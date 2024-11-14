<template>
	<Tooltip :disabled="!label" placement="right" :text="label" :hover-delay="0.1">
		<button class="flex gap-2 text-sm text-gray-600 hover:text-gray-900" v-bind="attrs">
			<FeatherIcon :name="icon" class="h-4 w-4" />
		</button>
	</Tooltip>
</template>

<script setup lang="ts">
import { FeatherIcon, Tooltip } from "frappe-ui"
import { useAttrs } from "vue"

defineProps<{
	icon: string
	label?: string
}>()

const attrs = useAttrs()
</script>
