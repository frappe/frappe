<template>
	<div
		class="relative flex h-full max-h-screen min-h-screen w-60 flex-col overflow-auto bg-gray-50 p-2"
	>
		<router-link
			class="mb-2 flex items-center gap-2 rounded p-2 hover:bg-gray-200"
			:to="{ name: 'Home' }"
			v-if="desktopItem"
		>
			<div class="rounded-sm p-1" :style="`background-color: ${desktopItem.color}`">
				<Icon :name="desktopItem?.icon" class="h-5 w-5 text-white" />
			</div>
			<span class="text-xl font-bold text-gray-800">{{ desktopItem?.label }}</span>
		</router-link>

		<!-- Workspaces -->
		<div class="mt-4 flex flex-col" v-if="sidebar.data?.workspaces">
			<div v-for="item in sidebar.data?.workspaces" :key="item.name">
				<div class="flex cursor-pointer items-center gap-2 rounded py-1 px-2 hover:bg-gray-200">
					<Icon :name="item.icon" class="h-5 w-5 text-gray-700" />
					<div class="flex items-center gap-1 text-base text-gray-700">
						{{ item.label }}
					</div>
				</div>
			</div>
		</div>

		<!-- Sections, Links, Spacers -->
		<div class="mt-4 flex flex-col" v-if="sidebar.data?.sections">
			<div v-for="item in sidebar.data?.sections" :key="item.name">
				<ModuleSidebarLink v-if="item.type === 'Link'" :link="item" />

				<div v-else-if="item.type === 'Spacer'" class="h-5"></div>

				<template v-else-if="item.type === 'Section Break' && item.links.length">
					<div class="mt-5 flex items-center gap-2 px-2" :class="item.opened ? 'mb-3' : ''">
						<FeatherIcon
							@click="item.opened = !item.opened"
							:name="item.opened ? 'chevron-down' : 'chevron-right'"
							class="h-4 w-4 font-semibold text-gray-600"
						/>
						<div class="flex items-center gap-1 text-sm uppercase text-gray-700">
							{{ item.label }}
						</div>
					</div>

					<ModuleSidebarLink
						v-if="item.opened"
						v-for="link in item.links"
						:key="link.name"
						:link="link"
					/>
				</template>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, watch } from "vue"
import { useRoute } from "vue-router"
import { createResource, FeatherIcon } from "frappe-ui"

import { getDesktopItem } from "@/data/desktop"
import Icon from "@/components/Icon.vue"
import ModuleSidebarLink from "@/components/ModuleSidebarLink.vue"

const route = useRoute()
const desktopItem = ref(null)

const sidebar = createResource({
	url: "frappe.api.desk.get_module_sidebar",
	transform(data) {
		data.sections.forEach((item) => {
			if (item.type === "Section Break") {
				item.opened = true
			}
		})
		return data
	},
})

watch(
	() => route.params.module,
	async (module) => {
		if (!module) return
		desktopItem.value = await getDesktopItem(module)
		sidebar.submit({ module: desktopItem.value.module })
	},
	{ immediate: true }
)
</script>
