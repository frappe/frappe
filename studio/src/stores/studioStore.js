import { ref, reactive, computed, nextTick } from "vue"
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
} from "@/utils/helpers"
import { studioPages } from "@/data/studioPages"
import { studioPageResources } from "@/data/studioResources"
import { studioAppScreens } from "@/data/studioApps"

const useStudioStore = defineStore("store", () => {
	const canvas = ref(null)
	const studioLayout = reactive({
		leftPanelWidth: 300,
		rightPanelWidth: 275,
		showLeftPanel: true,
		showRightPanel: true,
	})
	const activeBreakpoint = ref("desktop")
	const guides = reactive({
		showX: false,
		showY: false,
		x: 0,
		y: 0,
	})

	// block hover & selection
	const hoveredBlock = ref(null)
	const hoveredBreakpoint = ref(null)
	const selectedBlockIds = ref([])
	const selectedBlocks = computed(() => {
		return (
			selectedBlockIds.value
				.map((id) => canvas.value.findBlock(id))
				// filter out missing blocks/null values
				.filter((b) => b)
		)
	})

	function selectBlock(block, e, multiSelect = false) {
		if (multiSelect) {
			selectedBlockIds.value.push(block.componentId)
		} else {
			selectedBlockIds.value.splice(0, selectedBlockIds.value.length, block.componentId)
		}
	}

	// studio apps
	const activeApp = ref(null)
	const appScreens = ref([])

	async function setApp(appName) {
		const appDoc = await fetchApp(appName)
		activeApp.value = appDoc
		await setAppScreens(appName)
	}

	async function setAppScreens(appName) {
		studioAppScreens.filters = { parent: appName }
		await studioAppScreens.reload()
		appScreens.value = {}

		studioAppScreens.data.map((screen) => {
			appScreens.value[screen.screen_name] = screen
		})
	}

	// studio pages
	const activePage = ref(null)
	const pageBlocks = ref([])
	const selectedPage = ref(null)
	const savingPage = ref(false)
	const settingPage = ref(false)

	async function setPage(pageName) {
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
		canvas.value.setRootBlock(pageBlocks.value[0])

		nextTick(() => {
			settingPage.value = false
		})
	}

	function savePage() {
		pageBlocks.value = [canvas.value.getRootBlock()]
		const pageData = jsToJson(pageBlocks.value.map((block) => getBlockCopyWithoutParent(block)))

		const args = {
			name: selectedPage.value,
			draft_blocks: pageData,
		}
		return studioPages.setValue.submit(args).finally(() => {
			savingPage.value = false
		})
	}

	function updateActivePage(key, value) {
		if (!activePage.value) {
			return
		}
		return studioPages.setValue.submit(
			{ name: activePage.value.name, [key]: value },
			{
				onSuccess() {
					if (activePage.value) {
						activePage.value[key] = value
					}
				},
			},
		)
	}

	async function publishPage() {
		return studioPages.runDocMethod
			.submit({
				name: selectedPage.value,
				method: "publish",
			})
			.then(async () => {
				activePage.value = await fetchPage(selectedPage.value)
				openPageInBrowser(activePage.value)
			})
	}

	function openPageInBrowser(page) {
		let route = page.route
		window.open(`/${route}`, "studio-preview")
	}

	// styles
	const stylePropertyFilter = ref(null)

	// data
	const resources = ref({})

	async function setPageResources(page) {
		studioPageResources.filters = { parent: page.name }
		await studioPageResources.reload()
		resources.value = {}

		studioPageResources.data.map((resource) => {
			resources.value[resource.resource_name] = getNewResource(resource)
			resources.value[resource.resource_name].docname = resource.name
		})
	}

	return {
		// layout
		canvas,
		studioLayout,
		activeBreakpoint,
		guides,
		// block hover & selection
		hoveredBlock,
		hoveredBreakpoint,
		selectedBlockIds,
		selectedBlocks,
		selectBlock,
		pageBlocks,
		// studio app
		activeApp,
		setApp,
		appScreens,
		setAppScreens,
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
