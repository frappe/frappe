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
			/>
		</div>
	</div>
</template>

<script setup>
import { onActivated, watchEffect, watch, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useDebounceFn } from "@vueuse/core"
import { usePageMeta } from "frappe-ui"

import StudioToolbar from "@/components/StudioToolbar.vue"
import StudioLeftPanel from "@/components/StudioLeftPanel.vue"
import StudioRightPanel from "@/components/StudioRightPanel.vue"
import StudioCanvas from "@/components/StudioCanvas.vue"

import useStudioStore from "@/stores/studioStore"
import { studioPages } from "@/data/studioPages"
import { getRootBlock } from "@/utils/helpers"
import { studioAppScreens } from "@/data/studioApps"

const route = useRoute()
const router = useRouter()
const store = useStudioStore()

const canvas = ref(null)
watchEffect(() => {
	if (canvas.value) {
		store.canvas = canvas.value
	}
})

const debouncedPageSave = useDebounceFn(store.savePage, 300)
watch(
	() => canvas.value?.rootComponent,
	() => {
		if (store.selectedPage && !canvas.value?.canvasProps?.settingCanvas) {
			store.savingPage = true
			debouncedPageSave()
		}
	},
	{ deep: true },
)

onActivated(async () => {
	if (route.params.pageID === store.selectedPage) return

	if (route.params.pageID === "new") {
		await studioPages.insert
			.submit({
				page_title: "My Page",
				draft_blocks: [getRootBlock()],
			})
			.then(async (data) => {
				const appID = route.params.appID
				// add the newly created screen/page to the app's screens child table
				await studioAppScreens.insert.submit({
					screen: data.name,
					parent: appID,
					parenttype: "Studio App",
					parentfield: "screens",
				})

				router.push({ name: "StudioPage", params: { pageID: data.name }, force: true })
				store.setApp(appID)
				store.setPage(data.name)
			})
	} else {
		store.setApp(route.params.appID)
		await store.setPage(route.params.pageID)
	}
})

watch(
	() => route.params.pageID,
	() => {
		if (route.params.pageID === store.selectedPage) return
		store.setPage(route.params.pageID)
	},
	{ immediate: true },
)

usePageMeta(() => {
	return {
		title: `${store.activePage?.page_title} | Frappe Studio`,
	}
})
</script>

<style>
.studio {
	--toolbar-height: 3.5rem;
}
</style>
