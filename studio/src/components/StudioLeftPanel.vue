<template>
	<div class="flex flex-row overflow-auto shadow-lg">
		<!-- Primary Menu -->
		<div class="relative flex h-full w-12 flex-col space-y-2 border-r border-gray-200 bg-white p-3">
			<div
				class="flex items-center"
				v-for="tab in sidebarMenu"
				:key="tab.label"
				@click="setActiveTab(tab.label as LeftPanelOptions)"
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
		<transition
			enter-active-class="transition-all duration-300 ease-out"
			enter-from-class="-translate-x-3 opacity-0"
			enter-to-class="translate-x-0 opacity-100"
		>
			<div
				v-show="store.studioLayout.showLeftPanel"
				:style="{ width: `${store.studioLayout.leftPanelWidth - 48}px` }"
				class="overflow-auto border-r-[1px] pb-5 hide-scrollbar"
			>
				<PanelResizer
					:dimension="store.studioLayout.leftPanelWidth"
					side="right"
					:maxDimension="500"
					@resize="(width) => (store.studioLayout.leftPanelWidth = width)"
				/>
				<div
					class="sticky top-0 z-[12] flex justify-between border-b-[1px] border-gray-200 bg-white p-3 text-base font-semibold text-gray-800"
				>
					{{ activeTab }}
					<IconButton
						icon="chevrons-left"
						label="Collapse"
						@click="store.studioLayout.showLeftPanel = false"
					/>
				</div>

				<PagesPanel v-show="activeTab === 'Pages'" class="mx-2 my-3" />
				<ComponentPanel v-show="activeTab === 'Add Component'" class="mx-2 my-3" />
				<div v-show="activeTab === 'Layers'" class="p-4 pt-3">
					<ComponentLayers
						v-if="canvasStore.activeCanvas"
						class="no-scrollbar overflow-auto"
						ref="pageLayers"
						:blocks="[canvasStore.activeCanvas?.getRootBlock() as Block]"
					/>
				</div>

				<DataPanel v-show="activeTab === 'Data'" />

				<div v-show="activeTab === 'Code'">
					<CodePanel class="p-4" v-if="store.activePage" :page="store.activePage" :key="store.selectedPage" />
				</div>
			</div>
		</transition>
	</div>
</template>

<script setup lang="ts">
import { watch, computed, nextTick } from "vue"
import { Tooltip, FeatherIcon } from "frappe-ui"

import PagesPanel from "@/components/PagesPanel.vue"
import PanelResizer from "@/components/PanelResizer.vue"
import ComponentPanel from "@/components/ComponentPanel.vue"
import ComponentLayers from "@/components/ComponentLayers.vue"
import DataPanel from "@/components/DataPanel.vue"
import CodePanel from "@/components/CodePanel.vue"
import IconButton from "@/components/IconButton.vue"

import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import type { LeftPanelOptions } from "@/types"

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
const canvasStore = useCanvasStore()

const activeTab = computed(() => store.studioLayout.leftPanelActiveTab)

const setActiveTab = (tab: LeftPanelOptions) => {
	if (!store.studioLayout.showLeftPanel) {
		store.studioLayout.showLeftPanel = true
	}
	store.studioLayout.leftPanelActiveTab = tab
}

// moved out of ComponentLayers for performance
// TODO: Find a better way to do this
watch(
	() => canvasStore.activeCanvas?.hoveredBlock,
	(hoveredBlock) => {
		document.querySelectorAll(`[data-component-layer-id].hovered-block`).forEach((el) => {
			el.classList.remove("hovered-block")
		})
		if (hoveredBlock) {
			document.querySelector(`[data-component-layer-id="${hoveredBlock}"]`)?.classList.add("hovered-block")
		}
	},
)

watch(
	() => canvasStore.activeCanvas?.selectedBlocks,
	async () => {
		await nextTick()
		document.querySelectorAll(`[data-component-layer-id].block-selected`).forEach((el) => {
			el.classList.remove("block-selected")
		})
		if (canvasStore.activeCanvas?.selectedBlocks.length) {
			canvasStore.activeCanvas?.selectedBlocks.forEach((block: Block) => {
				document
					.querySelector(`[data-component-layer-id="${block.componentId}"]`)
					?.classList.add("block-selected")
			})
		}
	},
	{ deep: true },
)

watch(
	() => canvasStore.activeCanvas?.selectedSlot,
	async () => {
		await nextTick()
		document.querySelectorAll(`[data-slot-layer-id].slot-selected`).forEach((el) => {
			el.classList.remove("slot-selected")
		})
		if (canvasStore.activeCanvas?.selectedSlot) {
			document
				.querySelector(`[data-slot-layer-id="${canvasStore.activeCanvas?.selectedSlot.slotId}"]`)
				?.classList.add("slot-selected")
		}
	},
	{ deep: true },
)
</script>
