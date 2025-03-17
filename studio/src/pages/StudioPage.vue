<template>
	<div class="studio h-screen flex-col overflow-hidden bg-gray-100">
		<ComponentContextMenu ref="componentContextMenu"></ComponentContextMenu>
		<StudioToolbar class="relative z-30" />
		<div class="flex flex-col">
			<StudioLeftPanel
				class="absolute bottom-0 left-0 top-[var(--toolbar-height)] z-20 overflow-auto bg-white"
			/>

			<StudioCanvas
				ref="fragmentCanvas"
				:key="store.fragmentData.block?.componentId"
				v-if="store.editingMode === 'fragment' && store.fragmentData.block"
				:componentTree="store.fragmentData.block"
				:canvas-styles="{
					width: (store.fragmentData.block.getStyle('width') + '').endsWith('px') ? '!fit-content' : null,
					padding: '40px',
				}"
				:style="{
					left: `${store.studioLayout.showLeftPanel ? store.studioLayout.leftPanelWidth : 0}px`,
					right: `${store.studioLayout.showRightPanel ? store.studioLayout.rightPanelWidth : 0}px`,
				}"
				class="canvas-container absolute bottom-0 top-[var(--toolbar-height)] flex justify-center overflow-hidden bg-surface-gray-2 p-10"
			>
				<template v-slot:header>
					<div
						class="absolute left-0 right-0 top-0 z-20 flex items-center justify-between bg-surface-white p-2 text-sm text-ink-gray-8 shadow-sm"
					>
						<div class="flex items-center gap-1 pl-2 text-xs">
							<a class="cursor-pointer">Page</a>
							<FeatherIcon name="chevron-right" class="h-3 w-3" />
							<span class="flex items-center gap-2">
								{{ store.fragmentData.fragmentName }}
							</span>
						</div>
						<Button variant="solid" class="text-xs" @click="saveAndExitFragmentMode">
							{{ store.fragmentData.saveActionLabel || "Save" }}
						</Button>
					</div>
				</template>
			</StudioCanvas>

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
import { onActivated, watchEffect, watch, ref, onDeactivated, toRef } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useDebounceFn } from "@vueuse/core"
import { usePageMeta } from "frappe-ui"

import ComponentContextMenu from "@/components/ComponentContextMenu.vue"
import StudioToolbar from "@/components/StudioToolbar.vue"
import StudioLeftPanel from "@/components/StudioLeftPanel.vue"
import StudioRightPanel from "@/components/StudioRightPanel.vue"
import StudioCanvas from "@/components/StudioCanvas.vue"

import useStudioStore from "@/stores/studioStore"
import { studioPages } from "@/data/studioPages"
import { getRootBlock } from "@/utils/helpers"
import { StudioPage } from "@/types/Studio/StudioPage"
import { useStudioEvents } from "@/utils/useStudioEvents"

const route = useRoute()
const router = useRouter()
const store = useStudioStore()

const componentContextMenu = toRef(store, "componentContextMenu")
useStudioEvents()

const canvas = ref<InstanceType<typeof StudioCanvas> | null>(null)
watchEffect(() => {
	if (canvas.value) {
		store.canvas = canvas.value
	}
})

const fragmentCanvas = ref<InstanceType<typeof StudioCanvas> | null>(null)
async function saveAndExitFragmentMode(e: Event) {
	await store.fragmentData.saveAction?.(fragmentCanvas.value?.getRootBlock())
	fragmentCanvas.value?.toggleDirty(false)
	store.exitFragmentMode(e)
}

const debouncedPageSave = useDebounceFn(store.savePage, 300)
watch(
	() => canvas.value?.rootComponent,
	() => {
		if (
			store.selectedPage &&
			store.editingMode === "page" &&
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
				studio_app: route.params.appID as string,
			})
			.then(async (data: StudioPage) => {
				const appID = route.params.appID as string
				router.push({ name: "StudioPage", params: { appID: appID, pageID: data.name }, force: true })
				store.setApp(appID)
				await store.setPage(data.name)
			})
	} else {
		store.setApp(route.params.appID as string)
		await store.setPage(route.params.pageID as string)
	}
}

onActivated(() => {
	const pageID = route.params.pageID
	if (pageID && pageID !== store.selectedPage && pageID !== "new") {
		store.setApp(route.params.appID as string)
		store.setPage(pageID as string)
	}
})

onDeactivated(() => {
	store.selectedPage = null
	store.activePage = null
})

watch(
	() => route.params.pageID,
	async () => {
		await setPage()
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
