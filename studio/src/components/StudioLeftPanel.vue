<template>
	<div class="z-5 flex flex-row overflow-auto shadow-lg">
		<!-- Primary Menu -->
		<div class="relative flex h-full w-12 flex-col space-y-2 border-r border-gray-200 bg-white p-2">
			<div
				class="flex items-center"
				v-for="tab in sidebarMenu"
				:key="tab.label"
				@click="setActiveTab(tab.label)"
			>
				<Tooltip placement="right" :text="tab.label" :hover-delay="0.1">
					<div
						class="flex cursor-pointer items-center justify-center gap-2 truncate rounded px-3 py-1 transition duration-300 ease-in-out"
						:class="
							activeTab === tab.label ? 'bg-gray-100 text-gray-700' : 'text-gray-500 hover:text-gray-700'
						"
					>
						<FeatherIcon :name="tab.icon" class="h-6 w-6" />
					</div>
				</Tooltip>
			</div>
		</div>

		<!-- Secondary Menu -->
		<div :style="{ width: `${280 - 48}px` }">
			<div class="border-b-[1px] border-gray-200 p-3 text-base font-semibold text-gray-800">
				{{ activeTab }}
			</div>

			<ComponentPanel v-show="activeTab === 'Add Component'" class="mx-2 my-3" />
			<div v-show="activeTab === 'Layers'" class="p-4 pt-3">
				<ComponentLayers
					v-if="store.canvas"
					class="no-scrollbar overflow-auto"
					ref="pageLayers"
					:blocks="[store.canvas?.getRootBlock() as Block]"
				/>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Tooltip, FeatherIcon } from "frappe-ui"

import ComponentPanel from "@/components/ComponentPanel.vue"
import ComponentLayers from "./ComponentLayers.vue"

import Block from "@/utils/block"
import useStore from "@/store"

const sidebarMenu = [
	{
		label: "Add Component",
		icon: "plus-circle",
	},
	{
		label: "Layers",
		icon: "layers",
	},
	{
		label: "Data",
		icon: "database",
	},
	{
		label: "Code",
		icon: "code",
	},
]
const store = useStore()

const activeTab = ref("Add Component")
const setActiveTab = (tab) => {
	activeTab.value = tab
}
</script>
