<template>
	<Tooltip placement="right" :text="link.label" :hover-delay="0.1" :disabled="!isCollapsed">
		<router-link
			:to="link.route_to"
			class="flex cursor-pointer items-center gap-2 truncate rounded px-2 py-1 transition duration-300 ease-in-out"
			:class="[
				isCollapsed ? 'justify-center' : '',
				isActive ? 'bg-white shadow-sm' : 'hover:bg-gray-200',
			]"
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
import { useRoute, useRouter } from "vue-router"

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

const router = useRouter()
const route = useRoute()
const isActive = computed(() => {
	const linkRoute = router.resolve(props.link.route_to)
	// Check if the current route is the same as the link route, with optional trailing slash
	return route.path.match(new RegExp(`^${linkRoute.path}(/|$)`))
})
</script>
