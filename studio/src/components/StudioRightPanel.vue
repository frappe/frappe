<template>
	<div
		:style="{
			width: `${store.studioLayout.rightPanelWidth}px`,
		}"
	>
		<div class="relative min-h-full">
			<PanelResizer
				:dimension="store.studioLayout.rightPanelWidth"
				side="left"
				@resize="(width) => (store.studioLayout.rightPanelWidth = width)"
				:min-dimension="275"
				:max-dimension="400"
			/>

			<div class="sticky top-0 z-[12] flex w-full border-outline-elevation-2 bg-surface-base px-1 text-base">
				<!-- prettier-ignore -->
				<button
					v-for="tab of tabs"
					:key="tab"
					class="mx-2 py-3"
					@click="(store.studioLayout.rightPanelActiveTab = tab as RightPanelOptions)"
					:class="{
						'dark:border-zinc-500 dark:text-zinc-300 border-b-[1px] border-outline-gray-8': activeTab === tab,
						'dark:text-zinc-500 text-ink-gray-6': activeTab !== tab,
						'flex-1 px-2': !showInterfaceTab,
					}"
				>
					{{ tab }}
				</button>
			</div>

			<div
				v-if="showSearchInput"
				class="sticky top-[41px] z-50 mb-2 mt-[-15px] flex w-full bg-surface-base p-3"
			>
				<Input
					ref="searchInput"
					type="text"
					variant="outline"
					placeholder="Search properties"
					v-model="store.propertyFilter"
					@input="
						(value: string) => {
							store.propertyFilter = value
						}
					"
				/>
			</div>

			<ComponentProperties
				v-show="activeTab === 'Properties' || (activeTab === 'Styles' && combinePropsAndStylesTab)"
				class="p-3"
				:class="combinePropsAndStylesTab ? '!pb-0' : ''"
				:block="canvasStore.activeCanvas?.selectedBlocks[0]"
			/>
			<ComponentStyles
				v-show="activeTab === 'Styles'"
				class="p-3"
				:block="canvasStore.activeCanvas?.selectedBlocks[0]"
			/>
			<ComponentEvents
				v-show="activeTab === 'Events'"
				class="p-3"
				:block="canvasStore.activeCanvas?.selectedBlocks[0]"
			/>
			<ComponentInterface
				v-if="activeTab === 'Interface' && showInterfaceTab"
				class="p-3"
				@vue:unmounted="store.studioLayout.rightPanelActiveTab = 'Properties'"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"

import Input from "@/components/Input.vue"
import ComponentInterface from "@/components/ComponentInterface.vue"
import ComponentProperties from "@/components/ComponentProperties.vue"
import ComponentEvents from "@/components/ComponentEvents.vue"
import ComponentStyles from "@/components/ComponentStyles.vue"
import PanelResizer from "@/components/PanelResizer.vue"

import type { RightPanelOptions } from "@/types"
import blockController from "@/utils/blockController"

const store = useStudioStore()
const canvasStore = useCanvasStore()
const activeTab = computed(() => store.studioLayout.rightPanelActiveTab)

const showInterfaceTab = computed(() => canvasStore.editingMode === "component")
const combinePropsAndStylesTab = computed(
	() => blockController.isRoot() || blockController.isText() || blockController.isContainer(),
)
const tabs = computed(() => {
	let _tabs = showInterfaceTab.value
		? ["Interface", "Properties", "Styles", "Events"]
		: ["Properties", "Styles", "Events"]
	if (combinePropsAndStylesTab.value) {
		_tabs = _tabs.filter((tab) => tab !== "Properties")
	}
	return _tabs
})

const showSearchInput = computed(
	() =>
		(activeTab.value === "Properties" || activeTab.value === "Styles") &&
		blockController.isAnyBlockSelected(),
)
const searchInput = ref<InstanceType<typeof Input> | null>(null)
// command + f should focus on search input
window.addEventListener("keydown", (e) => {
	if (e.key === "f" && (e.metaKey || e.ctrlKey)) {
		e.preventDefault()
		searchInput.value?.$el?.querySelector("input")?.focus()
	}
})
</script>
