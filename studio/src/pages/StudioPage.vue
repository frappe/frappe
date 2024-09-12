<template>
	<div class="studio h-screen flex-col overflow-hidden bg-gray-100">
		<StudioToolbar class="relative z-30" />
		<div class="flex flex-col">
			<StudioLeftPanel
				class="absolute bottom-0 left-0 top-[var(--toolbar-height)] z-20 overflow-auto bg-white"
			/>
			<StudioCanvas
				ref="canvas"
				class="canvas-container absolute bottom-0 top-[var(--toolbar-height)] flex justify-center overflow-hidden bg-gray-200 p-10"
				v-if="store.pageBlocks[0]"
				:componentTree="store.pageBlocks[0]"
				:canvas-styles="{
					minHeight: '1000px',
				}"
				:style="{
					left: `${store.studioLayout.showLeftPanel ? store.studioLayout.leftPanelWidth : 0}px`,
					right: `${store.studioLayout.showRightPanel ? store.studioLayout.rightPanelWidth : 0}px`,
				}"
			/>
			<StudioRightPanel
				class="no-scrollbar dark:bg-zinc-900 absolute bottom-0 right-0 top-[var(--toolbar-height)] z-20 overflow-auto border-l-[1px] bg-white shadow-lg dark:border-gray-800"
			>
				></StudioRightPanel
			>
		</div>
	</div>
</template>

<script setup>
import { onActivated, watchEffect, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import StudioToolbar from "@/components/StudioToolbar.vue"
import StudioLeftPanel from "@/components/StudioLeftPanel.vue"
import StudioRightPanel from "@/components/StudioRightPanel.vue"
import StudioCanvas from "@/components/StudioCanvas.vue"

import useStore from "@/store"
import { studioPages } from "@/data/studioPages"
import { getRootBlock } from "@/utils/helpers"

const route = useRoute()
const router = useRouter()
const store = useStore()

const canvas = ref(null)
watchEffect(() => {
	if (canvas.value) {
		store.canvas = canvas.value
	}
})

onActivated(async () => {
	if (route.params.pageID === store.selectedPage) return

	if (route.params.pageID === "new") {
		await studioPages.insert
			.submit({
				page_title: "My Page",
				blocks: [getRootBlock()],
			})
			.then((data) => {
				router.push({ name: "StudioPage", params: { pageID: data.name }, force: true })
				store.setPage(data.name)
			})
	} else {
		await store.setPage(route.params.pageID)
	}
})
</script>

<style>
.studio {
	--left-panel-width: 17rem;
	--right-panel-width: 20rem;
	--toolbar-height: 3.5rem;
}
</style>
