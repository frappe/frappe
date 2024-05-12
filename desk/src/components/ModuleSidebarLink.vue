<template>
	<Tooltip placement="right" :text="link.label" :hover-delay="0.1" :disabled="!isCollapsed">
		<div
			class="flex cursor-pointer items-center gap-2 truncate rounded py-1 px-2 hover:bg-gray-200"
			:class="isCollapsed ? 'justify-center' : ''"
		>
			<Icon :name="link.icon" class="h-5 w-5 text-gray-700" />
			<div v-if="!isCollapsed" class="flex items-center gap-1 text-base text-gray-700">
				{{ link.label }}
			</div>
		</div>
	</Tooltip>
</template>

<script setup>
import { Tooltip } from "frappe-ui"
import Icon from "@/components/Icon.vue"

const props = defineProps({
	link: {
		type: Object,
		required: true,
	},
	isCollapsed: {
		type: Boolean,
		required: false,
		default: false,
	},
})
</script>
