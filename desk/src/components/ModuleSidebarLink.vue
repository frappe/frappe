<template>
	<Tooltip placement="right" :text="link.label" :hover-delay="0.1" :disabled="!isCollapsed">
		<router-link
			:to="routeTo"
			class="flex cursor-pointer items-center gap-2 truncate rounded px-2 py-1 hover:bg-gray-200"
			:class="isCollapsed ? 'justify-center' : ''"
		>
			<Icon :name="link.icon" class="h-5 w-5 text-gray-700" />
			<div v-if="!isCollapsed" class="flex items-center gap-1 text-base text-gray-700">
				{{ link.label }}
			</div>
		</router-link>
	</Tooltip>
</template>

<script setup>
import { Tooltip } from "frappe-ui"
import Icon from "@/components/Icon.vue"
import { computed } from "vue"
import { getRoute } from "@/utils/routing"

const props = defineProps({
	link: {
		type: Object,
		required: true,
	},
	module: {
		type: String,
		required: true,
	},
	isCollapsed: {
		type: Boolean,
		required: false,
		default: false,
	},
})

const routeTo = computed(() => getRoute(props.link, props.module))
</script>
