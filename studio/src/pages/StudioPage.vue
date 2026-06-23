<template>
	<div class="studio isolate h-screen flex-col overflow-hidden bg-surface-gray-2">
		<ComponentContextMenu ref="componentContextMenu"></ComponentContextMenu>
		<StudioToolbar class="relative z-30" />
		<div class="flex flex-col">
			<StudioLeftPanel
				class="absolute bottom-0 left-0 top-[var(--toolbar-height)] z-20 overflow-auto bg-surface-base"
			/>

			<StudioCanvas
				ref="fragmentCanvas"
				:key="canvasStore.fragmentData.block?.componentId"
				v-if="canvasStore.showFragmentCanvas && canvasStore.fragmentData.block"
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
						class="absolute left-0 right-0 top-0 z-20 flex items-center justify-between border-b border-outline-gray-2 bg-surface-base p-[0.4rem] text-sm text-ink-gray-8"
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

						<div class="ml-auto flex items-center gap-2">
							<Button
								v-if="canvasStore.editingMode === 'component'"
								variant="subtle"
								icon="lucide-settings"
								@click.prevent="store.studioLayout.rightPanelActiveTab = 'Interface'"
							></Button>
							<Button variant="subtle" class="text-xs" @click="canvasStore.exitFragmentMode">
								<template #prefix><FeatherIcon name="chevron-left" class="!h-3 !w-3" /></template>
								Page
							</Button>
							<Button variant="solid" class="text-xs" @click="saveFragmentMode">
								{{ canvasStore.fragmentData.saveActionLabel || "Save" }}
							</Button>
						</div>
					</div>
				</template>
			</StudioCanvas>

			<StudioCanvas
				v-show="canvasStore.editingMode === 'page'"
				ref="pageCanvas"
				v-if="store.pageBlocks[0]"
				class="canvas-container absolute bottom-0 top-[var(--toolbar-height)] flex justify-center overflow-hidden bg-surface-gray-3 p-10"
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
				class="no-scrollbar dark:bg-zinc-900 absolute bottom-0 right-0 top-[var(--toolbar-height)] z-20 overflow-auto border-l border-outline-gray-2 bg-surface-base dark:border-outline-gray-7"
			/>

			<!-- File explorer teleport for code editor -->
			<div id="studio-code-editor-outlet"></div>
		</div>

		<Dialog
			v-model="canvasStore.showHTMLDialog"
			class="overscroll-none"
			:title="`Edit HTML - ${canvasStore.editableBlock?.componentName}`"
			size="7xl"
		>
			<template #default>
				<Code
					:modelValue="canvasStore.editableBlock?.getHTML()"
					language="html"
					label="Edit HTML"
					:showLineNumbers="true"
					:showSaveButton="true"
					:completions="
						(context: CompletionContext) =>
							getCompletions(context, canvasStore.editableBlock?.getCompletions())
					"
					@save="
						(val: string) => {
							canvasStore.editableBlock?.setHTML(val)
							canvasStore.closeHTMLDialog()
						}
					"
					height="500px"
					max-height="500px"
					required
				/>
			</template>
		</Dialog>

		<Dialog
			v-model="canvasStore.showCodeDialog"
			class="overscroll-none"
			:title="`Edit ${canvasStore.editableBlock?.componentName} prop - ${canvasStore.editableCode.propName}`"
			size="7xl"
		>
			<template #default>
				<Code
					:modelValue="canvasStore.editableCode.code"
					language="javascript"
					label="Edit Code"
					:showLineNumbers="true"
					:showSaveButton="true"
					:completions="
						(context: CompletionContext) =>
							getCompletions(context, canvasStore.editableBlock?.getCompletions())
					"
					@save="
						(val) => {
							canvasStore.editableBlock?.setProp(canvasStore.editableCode.propName, val)
							canvasStore.showCodeDialog = false
						}
					"
					:emitOnChange="true"
					height="500px"
					max-height="500px"
					required
				/>
			</template>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import { onActivated, watchEffect, watch, ref, onDeactivated, toRef, nextTick } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useDebounceFn } from "@vueuse/core"
import { usePageMeta, Dialog } from "frappe-ui"
import type { CompletionContext } from "@codemirror/autocomplete"

import ComponentContextMenu from "@/components/ComponentContextMenu.vue"
import StudioToolbar from "@/components/StudioToolbar.vue"
import StudioLeftPanel from "@/components/StudioLeftPanel.vue"
import StudioRightPanel from "@/components/StudioRightPanel.vue"
import StudioCanvas from "@/components/StudioCanvas.vue"
import Code from "@/components/Code.vue"

import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { studioPages } from "@/data/studioPages"
import type { StudioPage } from "@/types/Studio/StudioPage"
import { useStudioEvents } from "@/utils/useStudioEvents"
import { getRootBlock } from "@/utils/serializer"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import { toast } from "frappe-ui"

const route = useRoute()
const router = useRouter()
const store = useStudioStore()
const canvasStore = useCanvasStore()

const getCompletions = useStudioCompletions()
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
				if (canvasStore.editingMode === "component") {
					store.studioLayout.rightPanelActiveTab = "Interface"
				}
			}
		})
	} else {
		canvasStore.activeCanvas = pageCanvas.value
	}
})

async function saveFragmentMode() {
	canvasStore.fragmentData.saveAction?.(fragmentCanvas.value?.getRootBlock())
	if (canvasStore.editingMode === "fragment") {
		toast.success(`${canvasStore.fragmentData.fragmentName} saved successfully`)
	}
}

const debouncedPageSave = useDebounceFn(store.savePage, 300)
watch(
	() => pageCanvas.value?.rootComponent,
	() => {
		if (
			store.selectedPage &&
			!pageCanvas.value?.canvasProps?.settingCanvas &&
			!store.settingPage &&
			!store.savingPage &&
			!canvasStore.isAIStreaming
		) {
			store.savingPage = true
			if (canvasStore.editingMode === "page") {
				debouncedPageSave()
			} else {
				store.savePage(pageCanvas.value?.getRootBlock())
			}
		}
	},
	{ deep: true },
)

async function setPage() {
	// capture route params up front — `setApp` is awaited below, and the route may change
	// during that await (e.g. navigating away), so we must not re-read route.params after it
	const appID = route.params.appID as string
	const pageID = route.params.pageID as string
	if (!pageID || pageID === store.selectedPage) return

	if (pageID === "new") {
		await studioPages.insert
			.submit({
				draft_blocks: [getRootBlock()],
				studio_app: appID,
			})
			.then(async (data: StudioPage) => {
				router.push({ name: "StudioPage", params: { appID: appID, pageID: data.name }, force: true })
				await store.setApp(appID)
				await store.setPage(data.name)
			})
	} else {
		await store.setApp(appID)
		await store.setPage(pageID)
	}
}

onActivated(async () => {
	const pageID = route.params.pageID
	if (pageID && pageID !== store.selectedPage && pageID !== "new") {
		await store.setApp(route.params.appID as string)
		await store.setPage(pageID as string)
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
	const page_title = store.activePage?.page_title
	return {
		title: page_title ? `${page_title} | Frappe Studio` : "Frappe Studio",
	}
})
</script>

<style>
.studio {
	--toolbar-height: 3.5rem;
}
</style>
