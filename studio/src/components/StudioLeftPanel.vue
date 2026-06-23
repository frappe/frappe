<template>
	<div class="flex flex-row overflow-auto border-r border-outline-gray-2">
		<!-- Primary Menu -->
		<div
			class="flex h-full w-12 flex-col items-center space-y-2 border-r border-outline-elevation-2 bg-surface-base p-3"
		>
			<Tooltip v-for="tab in sidebarMenu" :key="tab.label" placement="right" :text="tab.label">
				<Button
					:icon="tab.icon"
					size="md"
					:variant="store.studioLayout.leftPanelActiveTab === tab.label ? 'subtle' : 'ghost'"
					:class="{
						'!text-ink-gray-6': store.studioLayout.leftPanelActiveTab !== tab.label,
					}"
					@click.stop="setActiveTab(tab.label as LeftPanelOptions)"
				/>
			</Tooltip>
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
				class="flex flex-col overflow-auto border-r-[1px] hide-scrollbar"
			>
				<PanelResizer
					:dimension="store.studioLayout.leftPanelWidth"
					side="right"
					:maxDimension="500"
					@resize="(width) => (store.studioLayout.leftPanelWidth = width)"
				/>
				<div
					class="text-base-semibold sticky left-0 top-0 z-[12] flex w-full shrink-0 justify-between border-b-[1px] border-outline-elevation-2 bg-surface-base p-3 text-ink-gray-7"
				>
					{{ activeTab }}
					<IconButton
						:icon="LucideChevronsLeft"
						label="Collapse"
						@click="store.studioLayout.showLeftPanel = false"
					/>
				</div>

				<PagesPanel v-show="activeTab === 'Pages'" class="mx-2 my-3" />
				<ComponentPanel v-show="activeTab === 'Add Component'" class="mx-2 my-3" />
				<div v-show="activeTab === 'Layers'" class="p-3 pr-0">
					<ComponentLayers
						v-if="canvasStore.activeCanvas"
						class="w-fit min-w-full pr-3"
						ref="pageLayers"
						:blocks="[canvasStore.activeCanvas?.getRootBlock() as Block]"
					/>
				</div>

				<DataPanel v-show="activeTab === 'Data'" />

				<div v-show="activeTab === 'Code'">
					<CodePanel class="p-3" v-if="store.activePage" />
				</div>

				<AIChatPanel v-show="activeTab === 'AI Assistant'" />
			</div>
		</transition>
	</div>
</template>

<script setup lang="ts">
import { watch, computed, nextTick } from "vue"
import { Tooltip, Button } from "frappe-ui"

import PagesPanel from "@/components/PagesPanel.vue"
import PanelResizer from "@/components/PanelResizer.vue"
import ComponentPanel from "@/components/ComponentPanel.vue"
import ComponentLayers from "@/components/ComponentLayers.vue"
import DataPanel from "@/components/DataPanel.vue"
import CodePanel from "@/components/CodePanel.vue"
import IconButton from "@/components/IconButton.vue"
import LucideChevronsLeft from "~icons/lucide/chevrons-left"
import AIChatPanel from "@/components/AIChatPanel.vue"

import Block from "@/utils/block"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import type { LeftPanelOptions } from "@/types"

const sidebarMenu = [
	{
		label: "Pages",
		icon: "lucide-book",
	},
	{
		label: "Add Component",
		icon: "lucide-plus-circle",
	},
	{
		label: "Layers",
		icon: "lucide-layers",
	},
	{
		label: "Data",
		icon: "lucide-database",
	},
	{
		label: "Code",
		icon: "lucide-code",
	},
	{
		label: "AI Assistant",
		icon: "lucide-sparkle",
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
