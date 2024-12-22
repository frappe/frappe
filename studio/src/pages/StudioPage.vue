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

<script setup lang="ts">
import { onActivated, watchEffect, watch, ref, onDeactivated } from "vue"
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
import { studioAppPages } from "@/data/studioApps"
import { StudioPage } from "@/types/Studio/StudioPage"

const route = useRoute()
const router = useRouter()
const store = useStudioStore()

const canvas = ref<InstanceType<typeof StudioCanvas> | null>(null)
watchEffect(() => {
	if (canvas.value) {
		store.canvas = canvas.value
	}
})

const debouncedPageSave = useDebounceFn(store.savePage, 300)
watch(
	() => canvas.value?.rootComponent,
	() => {
		if (
			store.selectedPage &&
			!canvas.value?.canvasProps?.settingCanvas &&
			!store.settingPage &&
			!store.savingPage
		) {
			store.savingPage = true
			debouncedPageSave()
		}
	},
	{ deep: true },
)

async function setPage() {
	if (route.params.pageID === store.selectedPage) return

	if (route.params.pageID === "new") {
		await studioPages.insert
			.submit({
				page_title: "My Page",
				draft_blocks: [getRootBlock()],
			})
			.then(async (data: StudioPage) => {
				const appID = route.params.appID as string
				// add the newly created page to the app's pages child table
				await studioAppPages.insert.submit({
					studio_page: data.name,
					parent: appID,
					parenttype: "Studio App",
					parentfield: "pages",
				})

				router.push({ name: "StudioPage", params: { pageID: data.name }, force: true })
				store.setApp(appID)
				store.setPage(data.name)
			})
	} else {
		store.setApp(route.params.appID as string)
		await store.setPage(route.params.pageID as string)
	}
}

onActivated(() => setPage())

onDeactivated(() => {
	store.selectedPage = null
	store.activePage = null
})

watch(
	() => route.params.pageID,
	() => {
		setPage()
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
