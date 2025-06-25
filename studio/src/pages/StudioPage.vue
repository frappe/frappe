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
				:key="canvasStore.fragmentData.block?.componentId"
				v-if="canvasStore.editingMode === 'fragment' && canvasStore.fragmentData.block"
				:componentTree="canvasStore.fragmentData.block"
				:canvas-styles="{
					width: (canvasStore.fragmentData.block.getStyle('width') + '').endsWith('px')
						? '!fit-content'
						: null,
					padding: '40px',
					display: 'flex',
					justifyContent: 'center',
				}"
				:style="{
					left: `${store.studioLayout.showLeftPanel ? store.studioLayout.leftPanelWidth : 0}px`,
					right: `${store.studioLayout.showRightPanel ? store.studioLayout.rightPanelWidth : 0}px`,
				}"
				class="canvas-container bg-gray-2 absolute bottom-0 top-[var(--toolbar-height)] flex justify-center overflow-hidden p-10"
			>
				<template v-slot:header>
					<div
						class="absolute left-0 right-0 top-0 z-20 flex items-center justify-between bg-white p-[0.4rem] text-sm text-ink-gray-8 shadow-sm"
					>
						<div class="flex items-center gap-1 pl-2 text-xs">
							<a @click="canvasStore.exitFragmentMode" class="cursor-pointer">
								{{ store.activePage?.page_title }}
							</a>
							<FeatherIcon name="chevron-right" class="h-3 w-3" />
							<span class="flex items-center gap-2">
								{{ canvasStore.fragmentData.fragmentName }}
							</span>
						</div>
						<Button variant="solid" class="text-xs" @click="saveAndExitFragmentMode">
							{{ canvasStore.fragmentData.saveActionLabel || "Save" }}
						</Button>
					</div>
				</template>
			</StudioCanvas>

			<StudioCanvas
				v-show="canvasStore.editingMode === 'page'"
				ref="pageCanvas"
				v-if="store.pageBlocks[0]"
				class="canvas-container absolute bottom-0 top-[var(--toolbar-height)] flex justify-center overflow-hidden bg-gray-200 p-10"
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
import { onActivated, watchEffect, watch, ref, onDeactivated, toRef, nextTick } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useDebounceFn } from "@vueuse/core"
import { usePageMeta } from "frappe-ui"

import ComponentContextMenu from "@/components/ComponentContextMenu.vue"
import StudioToolbar from "@/components/StudioToolbar.vue"
import StudioLeftPanel from "@/components/StudioLeftPanel.vue"
import StudioRightPanel from "@/components/StudioRightPanel.vue"
import StudioCanvas from "@/components/StudioCanvas.vue"

import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { studioPages } from "@/data/studioPages"
import { getRootBlock } from "@/utils/helpers"
import type { StudioPage } from "@/types/Studio/StudioPage"
import { useStudioEvents } from "@/utils/useStudioEvents"

const route = useRoute()
const router = useRouter()
const store = useStudioStore()
const canvasStore = useCanvasStore()

const componentContextMenu = toRef(store, "componentContextMenu")
useStudioEvents()

const pageCanvas = ref<InstanceType<typeof StudioCanvas> | null>(null)
const fragmentCanvas = ref<InstanceType<typeof StudioCanvas> | null>(null)
watchEffect(() => {
	if (fragmentCanvas.value) {
		canvasStore.activeCanvas = fragmentCanvas.value
		nextTick(() => {
			const fragmentRootBlock = fragmentCanvas.value?.getRootBlock()
			if (fragmentRootBlock) {
				canvasStore.activeCanvas?.selectBlock(fragmentRootBlock, null)
			}
		})
	} else {
		canvasStore.activeCanvas = pageCanvas.value
	}
})

async function saveAndExitFragmentMode(e: Event) {
	canvasStore.fragmentData.saveAction?.(fragmentCanvas.value?.getRootBlock())
	canvasStore.exitFragmentMode(e)
	store.savePage()
}

const debouncedPageSave = useDebounceFn(store.savePage, 300)
watch(
	() => pageCanvas.value?.rootComponent,
	() => {
		if (
			store.selectedPage &&
			canvasStore.editingMode === "page" &&
			!pageCanvas.value?.canvasProps?.settingCanvas &&
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
