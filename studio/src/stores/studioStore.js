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
	confirm,
} from "@/utils/helpers"
import { studioPages } from "@/data/studioPages"
import { studioPageResources } from "@/data/studioResources"
import { studioApps, studioAppPages } from "@/data/studioApps"

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
	const appPages = ref([])

	async function setApp(appName) {
		const appDoc = await fetchApp(appName)
		activeApp.value = appDoc
		await setAppPages(appName)
	}

	async function setAppPages(appName) {
		studioAppPages.filters = { parent: appName }
		await studioAppPages.reload()
		appPages.value = {}

		studioAppPages.data.map((page) => {
			appPages.value[page.page_name] = page
		})
	}

	async function setAppHome(appName, pageName) {
		await studioApps.setValue.submit({ name: appName, app_home: pageName })
		setApp(appName)
	}

	async function deleteAppPage(appName, page) {
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

	function getAppPageRoute(pageName) {
		return Object.values(appPages.value).find((page) => page.page_name === pageName)?.route
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
					setAppPages(activeApp?.value?.name)
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

		const resourcePromises = studioPageResources.data.map(async (resource) => {
			const newResource = await getNewResource(resource)
			return {
				name: resource.resource_name,
				value: newResource,
				docname: resource.name,
			}
		})

		const resolvedResources = await Promise.all(resourcePromises)

		resolvedResources.forEach((item) => {
			resources.value[item.name] = item.value
		})
	}

	// actions
	const actions = ref({})
	const addAction = (action) => {}

	const removeAction = (action) => {}

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
		// actions
		actions,
		addAction,
		removeAction,
	}
})

export default useStudioStore
