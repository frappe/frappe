<template>
	<div class="z-5 flex flex-row overflow-auto shadow-lg">
		<!-- Primary Menu -->
		<div class="relative flex h-full w-12 flex-col space-y-2 border-r border-gray-200 bg-white p-3">
			<div
				class="flex items-center"
				v-for="tab in sidebarMenu"
				:key="tab.label"
				@click="store.studioLayout.leftPanelActiveTab = tab.label"
			>
				<Tooltip placement="right" :text="tab.label" :hover-delay="0.1">
					<div
						class="flex cursor-pointer items-center justify-center gap-2 truncate rounded px-3 py-1 transition duration-300 ease-in-out"
						:class="
							activeTab === tab.label ? 'bg-gray-100 text-gray-700' : 'text-gray-500 hover:text-gray-700'
						"
					>
						<FeatherIcon :name="tab.icon" class="h-5 w-5" />
					</div>
				</Tooltip>
			</div>
		</div>

		<!-- Secondary Menu -->
		<div
			:style="{ width: `${store.studioLayout.leftPanelWidth - 48}px` }"
			class="overflow-auto pb-5 hide-scrollbar"
		>
			<div
				class="sticky top-0 z-[12] border-b-[1px] border-gray-200 bg-white p-3 text-base font-semibold text-gray-800"
			>
				{{ activeTab }}
			</div>

			<PagesPanel v-show="activeTab === 'Pages'" class="mx-2 my-3" />
			<ComponentPanel v-show="activeTab === 'Add Component'" class="mx-2 my-3" />
			<div v-show="activeTab === 'Layers'" class="p-4 pt-3">
				<ComponentLayers
					v-if="store.canvas"
					class="no-scrollbar overflow-auto"
					ref="pageLayers"
					:blocks="[store.canvas?.getRootBlock() as Block]"
				/>
			</div>

			<DataPanel v-show="activeTab === 'Data'" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from "vue"
import { Tooltip, FeatherIcon } from "frappe-ui"

import PagesPanel from "@/components/PagesPanel.vue"
import ComponentPanel from "@/components/ComponentPanel.vue"
import ComponentLayers from "@/components/ComponentLayers.vue"

import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import DataPanel from "./DataPanel.vue"

const sidebarMenu = [
	{
		label: "Pages",
		icon: "book",
	},
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
const store = useStudioStore()

const activeTab = computed(() => store.studioLayout.leftPanelActiveTab)

// moved out of ComponentLayers for performance
// TODO: Find a better way to do this
watch(
	() => store.hoveredBlock,
	() => {
		document.querySelectorAll(`[data-component-layer-id].hovered-block`).forEach((el) => {
			el.classList.remove("hovered-block")
		})
		if (store.hoveredBlock) {
			document
				.querySelector(`[data-component-layer-id="${store.hoveredBlock}"]`)
				?.classList.add("hovered-block")
		}
	},
)

watch(
	() => store.selectedBlocks,
	() => {
		document.querySelectorAll(`[data-component-layer-id].block-selected`).forEach((el) => {
			el.classList.remove("block-selected")
		})
		if (store.selectedBlocks.length) {
			store.selectedBlocks.forEach((block: Block) => {
				document
					.querySelector(`[data-component-layer-id="${block.componentId}"]`)
					?.classList.add("block-selected")
			})
		}
	},
)
</script>
