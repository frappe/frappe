import { ref, reactive, computed, nextTick, Ref, watch } from "vue"
import { defineStore } from "pinia"

import {
	getBlockInstance,
	getRootBlock,
	jsToJson,
	getBlockCopyWithoutParent,
	jsonToJs,
	fetchApp,
	fetchPage,
	getNewResource,
	confirm,
} from "@/utils/helpers"
import { studioPages } from "@/data/studioPages"
import { studioPageResources } from "@/data/studioResources"
import { studioApps, studioAppPages } from "@/data/studioApps"

import StudioCanvas from "@/components/StudioCanvas.vue"
import Block from "@/utils/block"

import type { StudioApp } from "@/types/Studio/StudioApp"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { Resource } from "@/types/Studio/StudioResource"
import { LeftPanelOptions, RightPanelOptions, Slot } from "@/types"
import ComponentContextMenu from "@/components/ComponentContextMenu.vue"

const useStudioStore = defineStore("store", () => {
	const canvas = ref<InstanceType<typeof StudioCanvas> | null>(null)
	const studioLayout = reactive({
		leftPanelWidth: 300,
		rightPanelWidth: 275,
		showLeftPanel: true,
		showRightPanel: true,
		leftPanelActiveTab: <LeftPanelOptions>"Add Component",
		rightPanelActiveTab: <RightPanelOptions>"Properties",
	})
	const activeBreakpoint = ref("desktop")
	const guides = reactive({
		showX: false,
		showY: false,
		x: 0,
		y: 0,
	})
	const componentContextMenu = ref<InstanceType<typeof ComponentContextMenu> | null>(null)

	// block hover & selection
	const hoveredBlock = ref<string | null>(null)
	const hoveredBreakpoint = ref<string | null>(null)
	const selectedBlockIds = ref<string[]>([])
	const selectedBlocks = computed(() => {
		return (
			selectedBlockIds.value
				.map((id) => canvas.value?.findBlock(id))
				// filter out missing blocks/null values
				.filter((b) => b)
		)
	}) as Ref<Block[]>

	function selectBlock(block: Block, e: MouseEvent | null, multiSelect = false) {
		if (settingPage.value) return
		selectBlockById(block.componentId, e, multiSelect)
	}

	function selectBlockById(blockId: string, e: MouseEvent | null, multiSelect = false) {
		if (multiSelect) {
			selectedBlockIds.value.push(blockId)
		} else {
			selectedBlockIds.value.splice(0, selectedBlockIds.value.length, blockId)
		}
	}

	// drag & drop
	const isDragging = ref(false)
	const dropTarget = reactive({
		x: null as number | null,
		y: null as number | null,
		placeholder: null as HTMLElement | null,
		parentComponent: null as Block | null,
		index: null as number | null,
		slotName: null as string | null,
	})

	const handleDragStart = (ev: DragEvent, componentName: string) => {
		if (ev.target && ev.dataTransfer) {
			isDragging.value = true
			const ghostScale = canvas.value?.canvasProps.scale
			const ghostElement = (ev.target as HTMLElement).cloneNode(true) as HTMLElement
			ghostElement.id = "ghost"
			ghostElement.style.position = "fixed"
			ghostElement.style.transform = `scale(${ghostScale || 1})`
			ghostElement.style.pointerEvents = "none"
			ghostElement.style.zIndex = "999999"
			document.body.appendChild(ghostElement)

			// Set the scaled drag image
			ev.dataTransfer.setDragImage(ghostElement, 0, 0)
			// Clean up the ghost element
			setTimeout(() => {
				document.body.removeChild(ghostElement)
			}, 0)
			ev.dataTransfer.setData("componentName", componentName)

			let element = document.createElement("div")
			element.id = "placeholder"

			const root = document.querySelector(".__studio_component__[data-component-id='root']")
			if (root) {
				dropTarget.placeholder = root.appendChild(element)
			}
		}
	}

	const handleDragEnd = () => {
		const placeholder = document.getElementById("placeholder")
		if (placeholder) {
			placeholder.remove()
		}

		dropTarget.x = null
		dropTarget.y = null
		dropTarget.placeholder = null
		dropTarget.parentComponent = null
		dropTarget.index = null
		dropTarget.slotName = null

		isDragging.value = false
	}

	// slots
	const showSlotEditorDialog = ref(false)

	const selectedSlot = ref<Slot | null>()
	function selectSlot(slot: Slot) {
		selectedSlot.value = slot
		selectBlockById(slot.parentBlockId, null)
	}

	const activeSlotIds = computed(() => {
		const slotIds = new Set<string>()
		for (const block of selectedBlocks.value) {
			for (const slot of Object.values(block.componentSlots)) {
				slotIds.add(slot.slotId)
			}
		}
		return slotIds
	})

	watch(
		() => activeSlotIds.value,
		(map) => {
			// clear selected slot if the block is deleted, not selected anymore, or the slot is removed from the block
			if (selectedSlot.value && !map.has(selectedSlot.value.slotId)) {
				selectedSlot.value = null
			}
		},
		{ immediate: true }
	)

	// studio apps
	const activeApp = ref<StudioApp | null>(null)
	const appPages = ref<Record<string, StudioPage>>({})

	async function setApp(appName: string) {
		const appDoc = await fetchApp(appName)
		activeApp.value = appDoc
		await setAppPages(appName)
	}

	async function setAppPages(appName: string) {
		if (!appName) {
			return
		}
		studioAppPages.filters = { parent: appName }
		await studioAppPages.reload()
		appPages.value = {}

		studioAppPages.data.map((page: StudioPage) => {
			appPages.value[page.page_name] = page
		})
	}

	async function setAppHome(appName: string, pageName: string) {
		await studioApps.setValue.submit({ name: appName, app_home: pageName })
		setApp(appName)
	}

	async function deleteAppPage(appName: string, page: StudioPage) {
		// TODO: disallow deleting app home or app with only one page
		const confirmed = await confirm(`Are you sure you want to delete the page <b>${page.page_title}</b>?`)
		if (confirmed) {
			// delink page from app
			await studioAppPages.delete.submit(page.name)
			try {
				// try deleting the main page
				await studioPages.delete.submit(page.page_name)
			} catch (e) {
				// ignore error - might be linked to other apps
			}
			await setApp(appName)
		}
	}

	function getAppPageRoute(pageName: string) {
		return Object.values(appPages.value).find((page) => page.page_name === pageName)?.route
	}

	// studio pages
	const activePage = ref<StudioPage | null>(null)
	const pageBlocks = ref<Block[]>([])
	const selectedPage = ref<string | null>(null)
	const savingPage = ref(false)
	const settingPage = ref(false)

	async function setPage(pageName: string) {
		settingPage.value = true
		const page = await fetchPage(pageName)
		activePage.value = page

		const blocks = jsonToJs(page.draft_blocks || page.blocks || "[]")
		if (blocks.length === 0) {
			pageBlocks.value = [getRootBlock()]
		} else {
			pageBlocks.value = [getBlockInstance(blocks[0])]
		}
		selectedPage.value = page.name
		await setPageResources(page)
		canvas.value?.setRootBlock(pageBlocks.value[0])

		nextTick(() => {
			settingPage.value = false
		})
	}

	function savePage() {
		if (canvas.value) {
			pageBlocks.value = [canvas.value.getRootBlock()]
		}
		const pageData = jsToJson(pageBlocks.value.map((block) => getBlockCopyWithoutParent(block)))

		const args = {
			name: selectedPage.value,
			draft_blocks: pageData,
		}
		return studioPages.setValue.submit(args)
			.then((page: StudioPage) => {
				activePage.value = page
			})
			.finally(() => {
				savingPage.value = false
			})
	}

	function updateActivePage(key: string, value: string) {
		return studioPages.setValue.submit(
			{ name: activePage.value?.name, [key]: value },
			{
				onSuccess() {
					activePage.value![key] = value
					setAppPages(activeApp.value!.name)
				},
			},
		)
	}

	async function publishPage() {
		if (!selectedPage.value) return
		return studioPages.runDocMethod
			.submit({
				name: selectedPage.value,
				method: "publish",
			})
			.then(async () => {
				activePage.value = await fetchPage(selectedPage.value!)
				if (activePage.value) {
					openPageInBrowser(activePage.value)
				}
			})
	}

	function openPageInBrowser(page: StudioPage) {
		let route = page.route
		window.open(`/${route}`, "studio-preview")
	}

	// styles
	const stylePropertyFilter = ref<string | null>(null)

	// data
	const resources = ref<Record<string, Resource>>({})

	async function setPageResources(page: StudioPage) {
		studioPageResources.filters = { parent: page.name }
		await studioPageResources.reload()
		resources.value = {}

		const resourcePromises = studioPageResources.data.map(async (resource: Resource) => {
			const newResource = await getNewResource(resource)
			return {
				resource_name: resource.resource_name,
				value: newResource,
				resource_id: resource.resource_id,
				resource_child_table_id: resource.name,
			}
		})

		const resolvedResources = await Promise.all(resourcePromises)

		resolvedResources.forEach((item) => {
			resources.value[item.resource_name] = item.value
			if (!item.value) return
			resources.value[item.resource_name].resource_id = item.resource_id
			resources.value[item.resource_name].resource_child_table_id = item.resource_child_table_id
		})
	}

	return {
		// layout
		canvas,
		studioLayout,
		activeBreakpoint,
		guides,
		componentContextMenu,
		// block hover & selection
		hoveredBlock,
		hoveredBreakpoint,
		selectedBlockIds,
		selectedBlocks,
		selectBlock,
		selectBlockById,
		pageBlocks,
		dropTarget,
		isDragging,
		handleDragStart,
		handleDragEnd,
		// slots
		selectedSlot,
		selectSlot,
		showSlotEditorDialog,
		activeSlotIds,
		// studio app
		activeApp,
		setApp,
		setAppHome,
		deleteAppPage,
		appPages,
		setAppPages,
		getAppPageRoute,
		// studio pages
		selectedPage,
		settingPage,
		savingPage,
		activePage,
		setPage,
		savePage,
		updateActivePage,
		publishPage,
		openPageInBrowser,
		// styles
		stylePropertyFilter,
		// data
		resources,
		setPageResources,
	}
})

export default useStudioStore
