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

			<ComponentSettings v-if="showComponentSettings" class="p-3" />

			<div v-show="!showComponentSettings" class="sticky top-0 z-[12] w-full bg-surface-base">
				<div class="flex w-full border-outline-elevation-2 px-1 text-base">
					<!-- prettier-ignore -->
					<button
						v-for="tab of tabs"
						:key="tab"
						class="mx-2 flex-1 border-b px-2 py-3"
						@click="(store.studioLayout.rightPanelActiveTab = tab as RightPanelOptions)"
						:class="{
							'border-outline-gray-8 text-ink-gray-9': activeTab === tab,
							'border-transparent text-ink-gray-6': activeTab !== tab,
						}"
					>
						{{ tab }}
					</button>
				</div>

				<div v-if="showSearchInput" class="flex w-full p-3">
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
			</div>

			<ComponentProperties
				v-show="
					!showComponentSettings &&
					(activeTab === 'Properties' ||
						(activeTab === 'Styles' && combinePropsAndStylesTab && showPropertiesTab))
				"
				class="p-3"
				:class="combinePropsAndStylesTab ? '!pb-0' : ''"
				:block="canvasStore.activeCanvas?.selectedBlocks[0]"
			/>
			<ComponentStyles
				v-show="!showComponentSettings && activeTab === 'Styles'"
				class="p-3"
				:block="canvasStore.activeCanvas?.selectedBlocks[0]"
			/>
			<ComponentEvents
				v-show="!showComponentSettings && activeTab === 'Events'"
				class="p-3"
				:block="canvasStore.activeCanvas?.selectedBlocks[0]"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useKeyboardShortcut } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"

import Input from "@/components/Input.vue"
import ComponentSettings from "@/components/ComponentSettings.vue"
import ComponentProperties from "@/components/ComponentProperties.vue"
import ComponentEvents from "@/components/ComponentEvents.vue"
import ComponentStyles from "@/components/ComponentStyles.vue"
import PanelResizer from "@/components/PanelResizer.vue"

import type { RightPanelOptions } from "@/types"
import blockController from "@/utils/blockController"

const store = useStudioStore()
const canvasStore = useCanvasStore()
// The settings of the component that is open, while none of its blocks is selected.
const showComponentSettings = computed(
	() => canvasStore.editingMode === "component" && !blockController.isAnyBlockSelected(),
)
const showPropertiesTab = computed(() => !(blockController.isRoot() || blockController.isContainer()))
const combinePropsAndStylesTab = computed(() => blockController.isText())
const tabs = computed(() => {
	const _tabs = ["Properties", "Styles", "Events"]
	if (combinePropsAndStylesTab.value || !showPropertiesTab.value) {
		return _tabs.filter((tab) => tab !== "Properties")
	}
	return _tabs
})
const activeTab = computed(() => {
	const tab = store.studioLayout.rightPanelActiveTab
	return tabs.value.includes(tab) ? tab : tabs.value[0]
})

const showSearchInput = computed(
	() =>
		!showComponentSettings.value &&
		(activeTab.value === "Properties" || activeTab.value === "Styles") &&
		blockController.isAnyBlockSelected(),
)
const searchInput = ref<InstanceType<typeof Input> | null>(null)
useKeyboardShortcut({
	combo: "Mod+F",
	description: "Focus Property Search",
	group: "General",
	allowInInput: true,
	handler: () => searchInput.value?.$el?.querySelector("input")?.focus(),
})
</script>
