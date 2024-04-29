<template>
	<div
		class="relative flex h-full max-h-screen min-h-screen w-64 flex-col overflow-auto bg-gray-50 p-4"
	>
		<div class="flex items-center gap-2">
			<AppLogo class="h-6 w-6" />
			<span class="text-xl font-semibold text-gray-800">Frappe</span>
		</div>

		<div class="mt-1">
			<div v-for="(items, linkType) in sidebarLinks.data" :key="linkType">
				<div v-if="items.length" class="mt-7">
					<div class="text-base font-semibold text-gray-600">{{ linkType }}</div>
					<div class="mt-2 flex flex-col gap-1 pl-2">
						<div
							v-for="item in items"
							:key="item.link_to"
							class="cursor-pointer truncate rounded-md px-2 py-1 text-base text-gray-800 hover:bg-gray-100"
						>
							{{ item.label }}
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { watch } from "vue"
import { useRoute } from "vue-router"
import { createResource } from "frappe-ui"

import AppLogo from "@/components/icons/AppLogo.vue"

const route = useRoute()

const sidebarLinks = createResource({
	url: "frappe.api.desk.get_links_for_workspace",
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
