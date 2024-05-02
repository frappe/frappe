<template>
	<div
		class="relative flex h-full max-h-screen min-h-screen w-64 flex-col overflow-auto bg-gray-50 p-4"
	>
		<router-link class="mb-2 flex items-center gap-2" :to="{ name: 'Home' }">
			<AppLogo class="h-6 w-6" />
			<span class="text-xl font-semibold text-gray-800">Frappe</span>
		</router-link>

		<div v-for="group in sidebarLinks.data" :key="group.linkType">
			<!-- Link Group - DocTypes/Reports/Pages -->
			<div v-if="group.items.length" class="mt-5">
				<div class="flex items-center gap-1">
					<FeatherIcon
						@click="group.opened = !group.opened"
						:name="group.opened ? 'chevron-down' : 'chevron-right'"
						class="h-4 w-4 font-semibold text-gray-600"
					/>
					<div class="flex items-center gap-1 text-base font-semibold text-gray-600">
						{{ group.linkType }}
					</div>
				</div>

				<!-- Link Group Items -->
				<div v-if="group.opened" class="mt-2 flex flex-col pl-5">
					<div
						v-for="item in group.items"
						:key="item.link_to"
						class="cursor-pointer truncate border-l-2 px-2 py-1.5 text-base text-gray-800 hover:border-gray-900 hover:text-gray-900"
					>
						{{ item.label }}
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { watch } from "vue"
import { useRoute } from "vue-router"
import { createResource, FeatherIcon } from "frappe-ui"

import AppLogo from "@/components/icons/AppLogo.vue"

const route = useRoute()

const sidebarLinks = createResource({
	url: "frappe.api.desk.get_links_for_workspace",
	transform: (data) => {
		return Object.entries(data).map(([linkType, items]) => ({
			linkType,
			items,
			opened: true,
		}))
	},
})

watch(
	() => route.params.module,
	(module) => {
		if (!module) return
		sidebarLinks.submit({ workspace: module.toLowerCase() })
	},
	{ immediate: true }
)
</script>
