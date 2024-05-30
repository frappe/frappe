<template>
	<div class="invisible ml-auto flex items-center gap-1.5 text-gray-600 group-hover/item:visible">
		<button
			class="flex cursor-grabbing items-center rounded-sm p-1 text-gray-700 hover:bg-gray-300"
		>
			<Icon name="drag-sm" class="h-3 w-3" />
		</button>
		<Dropdown :options="itemActionMenu">
			<template v-slot="{ open }">
				<button
					class="flex items-center rounded-sm p-0.5 text-gray-700 hover:bg-gray-300"
					:class="open ? '!visible' : ''"
				>
					<FeatherIcon name="more-horizontal" class="h-4 w-4" />
				</button>
			</template>
		</Dropdown>
	</div>
</template>

<script setup>
import { inject } from "vue"
import { FeatherIcon, Dropdown } from "frappe-ui"
import Icon from "@/components/Icon.vue"

const props = defineProps({
	item: {
		type: Object,
		required: true,
	},
})

const updateSidebarItem = inject("updateSidebarItem")

const itemActionMenu = [
	{
		label: "Edit",
		icon: "edit",
		onClick: () => updateSidebarItem(props.item, "edit"),
		condition: () => props.item.type !== "Spacer",
	},
	{
		label: "Duplicate",
		icon: "copy",
		onClick: () => updateSidebarItem(props.item, "duplicate"),
	},
	{
		label: "Delete",
		icon: "trash",
		onClick: () => updateSidebarItem(props.item, "delete"),
	},
	{
		label: "Add Item Below",
		icon: "plus",
		onClick: () => updateSidebarItem(props.item, "addBelow"),
	},
]
</script>
