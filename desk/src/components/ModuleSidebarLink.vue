<template>
	<Tooltip placement="right" :text="link.label" :hover-delay="0.1" :disabled="!isCollapsed">
		<router-link
			:to="link.route_to"
			class="flex cursor-pointer items-center gap-2 truncate rounded px-2 transition duration-300 ease-in-out"
			:class="[
				isCollapsed ? 'justify-center' : '',
				isActive && !isEditing ? 'bg-white shadow-sm' : 'hover:bg-gray-200',
				isEditing ? 'group/item' : 'py-1',
			]"
		>
			<Icon :name="link.icon" class="h-5 w-5 text-gray-700" />
			<div v-if="!isCollapsed" class="flex items-center gap-1 truncate text-base text-gray-700">
				{{ link.label }}
			</div>

			<!-- Edit Menu -->
			<div
				v-if="isEditing"
				class="invisible ml-auto flex items-center gap-1 text-gray-600 group-hover/item:visible"
			>
				<Dropdown :options="itemActionMenu">
					<Button icon="more-horizontal" variant="subtle" size="sm" />
				</Dropdown>
			</div>
		</router-link>
	</Tooltip>
</template>

<script setup>
import { computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Tooltip, Dropdown } from "frappe-ui"
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
	isEditing: {
		type: Boolean,
		required: false,
		default: false,
	},
})

const emit = defineEmits(["update-sidebar-item"])

const router = useRouter()
const route = useRoute()

const itemActionMenu = [
	{
		label: "Edit",
		icon: "edit",
		onClick: () => emit("update-sidebar-item", props.link, "edit"),
	},
	{
		label: "Duplicate",
		icon: "copy",
		onClick: () => emit("update-sidebar-item", props.link, "duplicate"),
	},
	{
		label: "Delete",
		icon: "trash",
		onClick: () => emit("update-sidebar-item", props.link, "delete"),
	},
	{
		label: "Add Item Below",
		icon: "plus",
		onClick: () => emit("update-sidebar-item", props.link, "addBelow"),
	},
]

const isActive = computed(() => {
	const linkRoute = router.resolve(props.link.route_to)
	// Check if the current route is the same as the link route, with optional trailing slash
	return route.path.match(new RegExp(`^${linkRoute.path}(/|$)`))
})
</script>
