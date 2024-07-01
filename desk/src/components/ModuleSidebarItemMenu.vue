<template>
	<div
		class="invisible ml-auto flex items-center gap-1.5 text-gray-600 group-hover/item:visible has-[.active-item]:visible"
	>
		<button
			class="flex cursor-grabbing items-center rounded-sm p-1 text-gray-700 hover:bg-gray-300"
		>
			<Icon name="drag-sm" class="h-3 w-3" />
		</button>
		<Dropdown :options="itemActionMenu">
			<template v-slot="{ open }">
				<button
					class="flex cursor-pointer items-center rounded-sm p-0.5 text-gray-700 hover:bg-gray-300"
					:class="open ? 'active-item' : ''"
				>
					<FeatherIcon name="more-horizontal" class="h-4 w-4" />
				</button>
			</template>
		</Dropdown>
	</div>
</template>

<script setup lang="ts">
import { inject } from "vue"
import { Dropdown } from "frappe-ui"
import Icon from "@/components/Icon.vue"

import { ModuleSidebarItem } from "@/types"
import { updateSidebarItemFnKey } from "@/types/injectionKeys"

const props = defineProps<{ item: ModuleSidebarItem }>()

const updateSidebarItem = inject(updateSidebarItemFnKey, () => {})

const itemActionMenu = [
	{
		label: "Edit",
		icon: "edit",
		onClick: () => updateSidebarItem(props.item, "edit"),
		condition: () => props.item.type !== "Spacer",
	},
	{
		label: "Add Item Below",
		icon: "plus",
		onClick: () => updateSidebarItem(props.item, "addBelow"),
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
]
</script>
