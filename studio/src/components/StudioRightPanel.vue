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

			<div class="sticky top-0 z-[12] flex w-full border-gray-200 bg-white px-2 text-base">
				<button
					v-for="tab of ['Properties', 'Events', 'Styles']"
					:key="tab"
					class="mx-2 flex-1 p-2 py-3"
					@click="store.studioLayout.rightPanelActiveTab = tab as RightPanelOptions"
					:class="{
						'dark:border-zinc-500 dark:text-zinc-300 border-b-[1px] border-gray-900': activeTab === tab,
						'dark:text-zinc-500 text-gray-700': activeTab !== tab,
					}"
				>
					{{ tab }}
				</button>
			</div>

			<ComponentProps
				v-show="activeTab === 'Properties'"
				class="p-4"
				:block="canvasStore.activeCanvas?.selectedBlocks[0]"
			/>
			<ComponentEvents
				v-show="activeTab === 'Events'"
				class="p-4"
				:block="canvasStore.activeCanvas?.selectedBlocks[0]"
			/>
			<ComponentStyles
				v-show="activeTab === 'Styles'"
				class="p-4"
				:block="canvasStore.activeCanvas?.selectedBlocks[0]"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"

import ComponentProps from "@/components/ComponentProps.vue"
import ComponentEvents from "@/components/ComponentEvents.vue"
import ComponentStyles from "@/components/ComponentStyles.vue"
import PanelResizer from "@/components/PanelResizer.vue"

import type { RightPanelOptions } from "@/types"

const store = useStudioStore()
const canvasStore = useCanvasStore()
const activeTab = computed(() => store.studioLayout.rightPanelActiveTab)
</script>
