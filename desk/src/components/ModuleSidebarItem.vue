<template>
	<div>
		<Tooltip
			placement="right"
			:text="item.label"
			:hover-delay="0.1"
			:disabled="!isCollapsed"
			v-if="type === 'Link'"
		>
			<router-link
				:to="item.route_to"
				class="flex items-center gap-2 truncate rounded px-2 py-1 transition duration-300 ease-in-out"
				:class="[
					isCollapsed ? 'justify-center' : '',
					isActive && !isEditing ? 'bg-white shadow-sm' : 'hover:bg-gray-200',
					isEditing
						? 'group/item cursor-grabbing has-[.active-item]:bg-gray-200'
						: 'cursor-pointer',
				]"
			>
				<Icon :name="item.icon || 'folder-normal'" class="h-5 w-5 text-gray-700" />
				<div v-if="!isCollapsed" class="flex items-center gap-1 truncate text-base text-gray-700">
					{{ item.label }}
				</div>
				<ModuleSidebarItemMenu :item="item" v-if="showEditMenu" />
			</router-link>
		</Tooltip>

		<template v-else-if="type === 'Spacer'">
			<div
				v-if="isEditing"
				class="group/item ml-2 flex min-h-6 cursor-grabbing items-center justify-center rounded border-dashed border-gray-400 px-2 text-xs uppercase text-gray-600 hover:border has-[.active-item]:border"
			>
				<ModuleSidebarItemMenu :item="item" />
			</div>
			<div v-else class="h-5"></div>
		</template>

		<div v-else-if="type === 'Section Break' && item.links?.length">
			<div v-if="isCollapsed" class="mx-2 my-2 h-1 border-b"></div>
			<div
				v-else
				class="group/item mt-5 flex items-center gap-2 px-2"
				:class="item.opened ? 'mb-2' : ''"
			>
				<div
					@click="item.opened = !item.opened"
					class="flex items-center gap-2"
					:class="isEditing ? 'cursor-grabbing' : 'cursor-pointer'"
				>
					<FeatherIcon
						:name="item.opened ? 'chevron-down' : 'chevron-right'"
						class="h-4 w-4 font-semibold text-gray-600"
					/>
					<div class="flex items-center gap-1 text-sm uppercase text-gray-700">
						{{ item.label }}
					</div>
				</div>
				<ModuleSidebarItemMenu :item="item" v-if="showEditMenu" />
			</div>

			<nav v-if="item.opened" class="flex flex-col space-y-0.5">
				<ModuleSidebarItem
					v-for="link in item.links"
					type="Link"
					:key="link.name"
					:item="link"
					:isCollapsed="isCollapsed"
					:isEditing="isEditing"
					:hideEditMenu="true"
				/>
			</nav>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Tooltip, FeatherIcon } from "frappe-ui"
import Icon from "@/components/Icon.vue"
import ModuleSidebarItemMenu from "@/components/ModuleSidebarItemMenu.vue"

const props = defineProps({
	type: {
		type: String,
		required: true,
	},
	item: {
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
	hideEditMenu: {
		type: Boolean,
		required: false,
		default: false,
	},
})

const router = useRouter()
const route = useRoute()

const showEditMenu = computed(() => {
	return props.isEditing && !props.isCollapsed && !props.hideEditMenu && props.type !== "Spacer"
})

const isActive = computed(() => {
	const linkRoute = router.resolve(props.item.route_to)
	// Check if the current route is the same as the link route, with optional trailing slash
	return route.path.match(new RegExp(`^${linkRoute.path}(/|$)`))
})
</script>
