import { ref, reactive, nextTick, computed } from "vue"
import router from "@/router/studio_router"
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
	getInitialVariableValue,
} from "@/utils/helpers"
import { studioPages } from "@/data/studioPages"
import { studioPageResources } from "@/data/studioResources"
import { studioApps } from "@/data/studioApps"

import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"

import type { StudioApp } from "@/types/Studio/StudioApp"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { Resource } from "@/types/Studio/StudioResource"
import type { LeftPanelOptions, RightPanelOptions, SelectOption, StudioMode } from "@/types"
import ComponentContextMenu from "@/components/ComponentContextMenu.vue"
import { studioVariables } from "@/data/studioVariables"
import type { Variable } from "@/types/Studio/StudioPageVariable"
import { toast } from "vue-sonner"
import { createResource } from "frappe-ui"

const useStudioStore = defineStore("store", () => {
	const studioLayout = reactive({
		leftPanelWidth: 300,
		rightPanelWidth: 275,
		showLeftPanel: true,
		showRightPanel: true,
		leftPanelActiveTab: <LeftPanelOptions>"Add Component",
		rightPanelActiveTab: <RightPanelOptions>"Properties",
	})
	const mode = ref<StudioMode>("select")
	const componentContextMenu = ref<InstanceType<typeof ComponentContextMenu> | null>(null)

	// dialogs
	const showSlotEditorDialog = ref(false)

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
		studioPages.filters = { studio_app : appName }
		await studioPages.reload()
		appPages.value = {}

		studioPages.data.map((page: StudioPage) => {
			appPages.value[page.name] = page
		})
	}

	function updateActiveApp(key: string, value: string) {
		studioApps.setValue.submit(
			{ name: activeApp.value?.name, [key]: value },
			{
				onSuccess() {
					setApp(activeApp.value!.name)
				},
			},
		)
	}

	async function deleteAppPage(appName: string, page: StudioPage) {
		const isHome = activeApp.value?.app_home === page.name
		if (isHome) {
			toast.error("Cannot delete this page because it is set as the App Home.")
			return
		}

		const confirmed = await confirm(`Are you sure you want to delete the page <b>${page.page_title}</b>?`)
		if (confirmed) {
			try {
				await studioPages.delete.submit(page.name)
				await setApp(appName)
				toast.success(`Page "${page.page_title}" deleted successfully`)
			} catch (error) {
				toast.error("An unexpected error occurred while deleting the page.")
			}
		}
	}

	async function duplicateAppPage(appName: string, page: StudioPage) {
		toast.promise(
			createResource({
				url: "studio.studio.doctype.studio_page.studio_page.duplicate_page",
				method: "POST",
				params: {
					page_name: page.name,
					app_name: appName,
				}
			}).fetch(),
			{
				loading: "Duplicating page",
				success: (page: StudioPage) => {
					// load page and refresh
					router.push({
						name: "StudioPage",
						params: { appID: appName, pageID: page.name },
					})
					return `Page "${page.page_title}" duplicated successfully`
				},
			},
		)
	}

	function getAppPageRoute(pageName: string) {
		return Object.values(appPages.value).find((page) => page.name === pageName)?.route
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
		await setPageData(page)

		const canvasStore = useCanvasStore()
		canvasStore.activeCanvas?.setRootBlock(pageBlocks.value[0])
		canvasStore.activeCanvas?.clearSelection()

		nextTick(() => {
			settingPage.value = false
		})
	}

	function savePage() {
		const canvasStore = useCanvasStore()
		if (canvasStore?.activeCanvas) {
			pageBlocks.value = [canvasStore.activeCanvas.getRootBlock()]
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

		await generateAppBuild()
		return studioPages.runDocMethod
			.submit(
				{
					name: selectedPage.value,
					method: "publish",
				},
				{
					onError(error: any) {
						toast.error("Failed to publish the page", {
							description: error.messages.join(", "),
							duration: Infinity,
							action: {
								label: "Edit Pages",
								onClick: () => {
									studioLayout.leftPanelActiveTab = "Pages"
								}
							}
						})
					},
				}
			)
			.then(async () => {
				activePage.value = await fetchPage(selectedPage.value!)
				if (activeApp.value && activePage.value) {
					openPageInBrowser(activeApp.value, activePage.value)
				}
			})
	}

	function openPageInBrowser(app: StudioApp, page: StudioPage, preview: boolean = false) {
		let route = `/${app.route}${page.route}`
		if (preview) {
			route = `/dev${route}`
		}
		if (import.meta.env.DEV) {
			route = `${window.site_url}${route}`
		}

		const targetWindow = window.open(route, "studio-preview")
		if (targetWindow?.location.pathname === route) {
			targetWindow?.location.reload()
		} else {
			setTimeout(() => {
				targetWindow?.location.reload()
			}, 50)
		}
	}

	// build
	function generateAppBuild() {
		if (!activeApp.value) return
		return studioApps.runDocMethod.submit({
			name: activeApp.value.name,
			method: "generate_app_build",
		}, {
			onSuccess() {
				toast.success("App build generated")
			},
			onError(error: any) {
				toast.error("Failed to generate app build", {
					description: error?.messages?.join(", "),
					duration: Infinity,
				})
			},
		})
	}

	// styles
	const stylePropertyFilter = ref<string | null>(null)

	// data
	const resources = ref<Record<string, Resource>>({})
	const variableConfigs = ref<Record<string, Variable>>({})
	const variables = ref<Record<string, any>>({})

	async function setPageData(page: StudioPage) {
		await setPageResources(page)
		await setPageVariables(page)
	}

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

	async function setPageVariables(page: StudioPage) {
		studioVariables.filters = { parent: page.name }
		await studioVariables.reload()
		variableConfigs.value = {}
		variables.value = {}

		studioVariables.data.map((variable: Variable) => {
			variableConfigs.value[variable.variable_name] = {
				...variable,
				initial_value: getInitialVariableValue(variable),
			}
			variables.value[variable.variable_name] = getInitialVariableValue(variable)
		})
	}

	const variableOptions = computed(() => {
		const options: SelectOption[] = []

		function traverse(obj: any, path = "") {
			for (const key in obj) {
				const currentPath = path ? `${path}.${key}` : key
				options.push({ value: currentPath, label: currentPath })

				if (typeof obj[key] === "object" && obj[key] !== null) {
					// add nested properties
					traverse(obj[key], currentPath)
				}
			}
		}

		traverse(variables.value)
		return options
	})

	return {
		// layout
		studioLayout,
		mode,
		componentContextMenu,
		// dialogs
		showSlotEditorDialog,
		// studio app
		activeApp,
		setApp,
		updateActiveApp,
		deleteAppPage,
		duplicateAppPage,
		appPages,
		setAppPages,
		getAppPageRoute,
		// studio pages
		pageBlocks,
		selectedPage,
		settingPage,
		savingPage,
		activePage,
		setPage,
		savePage,
		updateActivePage,
		publishPage,
		openPageInBrowser,
		// app build
		generateAppBuild,
		// styles
		stylePropertyFilter,
		// data
		resources,
		variables,
		variableConfigs,
		setPageData,
		setPageResources,
		setPageVariables,
		variableOptions,
	}
})

export default useStudioStore
