<template>
	<div class="flex flex-row shadow-lg z-5 overflow-auto">
		<!-- Primary Menu -->
		<div class="relative flex flex-col space-y-2 bg-white w-12 p-2 h-full border-r border-gray-200">
			<div
				class="flex items-center"
				v-for="tab in sidebarMenu"
				:key="tab.label"
				@click="setActiveTab(tab.label)"
			>
				<Tooltip placement="right" :text="tab.label" :hover-delay="0.1">
					<div
						class="flex items-center justify-center cursor-pointer gap-2 truncate rounded px-3 py-1 transition duration-300 ease-in-out"
						:class="{ 'bg-gray-100': activeTab === tab.label }"
					>
						<FeatherIcon :name="tab.icon" class="h-6 w-6 text-gray-600" />
					</div>
				</Tooltip>
			</div>
		</div>

		<!-- Secondary Menu -->
		<div :style="{ width: `${280 - 48}px` }">
			<div class="text-base font-semibold text-gray-800 p-3 border-b-[1px] border-gray-200">
				{{ activeTab }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue"
import { Tooltip, FeatherIcon } from "frappe-ui"

const activeTab = ref("Add Component")
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

const setActiveTab = (tab) => {
	activeTab.value = tab
}
</script>
