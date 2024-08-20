<template>
	<div class="studio h-screen flex-col overflow-hidden bg-gray-100">
		<StudioToolbar class="relative z-30" />
		<div class="flex flex-col">
			<StudioLeftPanel class="absolute bottom-0 left-0 top-[var(--toolbar-height)] bg-white" />
			<StudioCanvas
				class="canvas-container absolute bottom-0 left-[280px] right-[275px] top-[var(--toolbar-height)] flex justify-center overflow-hidden bg-gray-200 p-10"
				v-if="store.pageBlocks[0]"
				:componentTree="store.pageBlocks[0]"
			/>
		</div>
	</div>
</template>

<script setup>
import { onActivated } from "vue"
import { useRoute, useRouter } from "vue-router"

import StudioToolbar from "@/components/StudioToolbar.vue"
import StudioLeftPanel from "@/components/StudioLeftPanel.vue"
import StudioCanvas from "@/components/StudioCanvas.vue"

import useStore from "@/store"
import { studioPages } from "@/data/studioPages"
import { getRootBlock } from "@/utils/helpers"

const route = useRoute()
const router = useRouter()
const store = useStore()

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
