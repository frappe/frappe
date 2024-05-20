<template>
	<div
		class="relative flex h-full max-h-screen min-h-screen flex-col overflow-auto bg-gray-50 px-2 pt-2"
		:class="isCollapsed ? 'w-15' : 'w-60'"
	>
		<router-link
			class="mb-1 flex items-center gap-2 rounded p-2 hover:bg-gray-200"
			:to="{ name: 'Home' }"
			v-if="desktopItem"
		>
			<div class="rounded-sm p-1" :style="`background-color: ${desktopItem.color}`">
				<Icon :name="desktopItem?.icon" class="h-5 w-5 text-white" />
			</div>
			<span v-if="!isCollapsed" class="text-xl font-bold text-gray-800">
				{{ desktopItem?.label }}
			</span>
		</router-link>

		<!-- Workspaces -->
		<div class="mt-4 flex flex-col" v-if="sidebar.data?.workspaces">
			<ModuleSidebarLink
				v-for="item in sidebar.data?.workspaces"
				:key="item.name"
				:link="item"
				:isCollapsed="isCollapsed"
			/>
		</div>

		<!-- Sections, Links, Spacers -->
		<div class="mt-4 flex flex-col" v-if="sidebar.data?.sections">
			<div v-for="item in sidebar.data?.sections" :key="item.name">
				<ModuleSidebarLink v-if="item.type === 'Link'" :link="item" :isCollapsed="isCollapsed" />

				<div v-else-if="item.type === 'Spacer'" class="h-5"></div>

				<template v-else-if="item.type === 'Section Break' && item.links.length">
					<div v-if="isCollapsed" class="mx-2 my-2 h-1 border-b"></div>
					<div v-else class="mt-5 flex items-center gap-2 px-2" :class="item.opened ? 'mb-3' : ''">
						<FeatherIcon
							@click="item.opened = !item.opened"
							:name="item.opened ? 'chevron-down' : 'chevron-right'"
							class="h-4 w-4 cursor-pointer font-semibold text-gray-600"
						/>
						<div class="flex items-center gap-1 text-sm uppercase text-gray-700">
							{{ item.label }}
						</div>
					</div>

					<template v-if="item.opened">
						<ModuleSidebarLink
							v-for="link in item.links"
							:key="link.name"
							:link="link"
							:isCollapsed="isCollapsed"
						/>
					</template>
				</template>
			</div>
		</div>

		<div class="sticky bottom-0 my-1 mt-auto flex flex-col items-start gap-1 bg-gray-50 py-2">
			<button
				class="flex w-full gap-2 rounded p-2 text-sm uppercase text-gray-700 hover:bg-gray-200"
				:class="isCollapsed ? 'justify-center' : ''"
				@click="isCollapsed = !isCollapsed"
			>
				<FeatherIcon
					:name="isCollapsed ? 'arrow-right' : 'arrow-left'"
					class="h-4 w-4 text-gray-600"
				/>
				<span v-if="!isCollapsed">Collapse</span>
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue"
import { FeatherIcon } from "frappe-ui"

import Icon from "@/components/Icon.vue"
import ModuleSidebarLink from "@/components/ModuleSidebarLink.vue"

import { getDesktopItem, sidebar } from "@/data/desktop"

const props = defineProps({
	module: {
		type: String,
		required: true,
	},
})

const desktopItem = ref(null)
const isCollapsed = ref(false)

async function getSidebar(module) {
	desktopItem.value = await getDesktopItem(module)
	sidebar.submit({ module: module })
}
getSidebar(props.module)
</script>
