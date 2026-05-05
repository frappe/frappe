import { ref, reactive, nextTick, computed, toRaw } from "vue"
import router from "@/router/studio_router"
import { defineStore } from "pinia"

import {
	fetchApp,
	fetchPage,
	confirm,
	getInitialVariableValue,
} from "@/utils/helpers"
import { getBlockInstance, getRootBlock, getBlockCopyWithoutParent, jsToJson } from "@/utils/serializer"
import { studioPages } from "@/data/studioPages"
import { studioApps } from "@/data/studioApps"
import { studioVariables } from "@/data/studioVariables"

import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import useCodeStore from "@/stores/codeStore"
import { registerCustomVueComponents, unregisterCustomVueComponents } from "@/globals"
import type { CustomVueComponentMeta } from "@/types/vue"

import type { StudioApp } from "@/types/Studio/StudioApp"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { LeftPanelOptions, RightPanelOptions, leftPanelComponentTabOptions, StudioMode } from "@/types"
import ComponentContextMenu from "@/components/ComponentContextMenu.vue"
import type { Variable, VariableOption } from "@/types/Studio/StudioPageVariable"
import { toast } from "vue-sonner"
import { createResource } from "frappe-ui"

const useStudioStore = defineStore("store", () => {
	const studioLayout = reactive({
		leftPanelWidth: 338,
		rightPanelWidth: 275,
		showLeftPanel: true,
		showRightPanel: true,
		leftPanelActiveTab: <LeftPanelOptions>"Add Component",
		leftPanelComponentTab: <leftPanelComponentTabOptions>"Standard",
		rightPanelActiveTab: <RightPanelOptions>"Properties",
	})
	const mode = ref<StudioMode>("select")
	const componentContextMenu = ref<InstanceType<typeof ComponentContextMenu> | null>(null)

	// dialogs
	const showSlotEditorDialog = ref(false)
	const showSearchBlock = ref(false)

	// studio apps
	const activeApp = ref<StudioApp | null>(null)
	const appPages = ref<Record<string, StudioPage>>({})
	const customVueComponents = ref<CustomVueComponentMeta[]>([])

	async function setApp(appName: string) {
		const appDoc = await fetchApp(appName)
		activeApp.value = appDoc
		await setAppPages(appName)
		await loadCustomVueComponents()
		setupCustomComponentListener()
	}

	async function loadCustomVueComponents() {
		if (customVueComponents.value.length) {
			unregisterCustomVueComponents(customVueComponents.value)
			customVueComponents.value = []
		}
		const frappeApp = activeApp.value?.frappe_app
		if (!frappeApp) return

		customVueComponents.value = await registerCustomVueComponents(frappeApp)
	}

	function setupCustomComponentListener() {
		if (activeApp.value?.is_standard && import.meta.hot) {
			// Auto-refresh custom components when .vue files are added/removed/renamed in studio folders
			import.meta.hot.on("studio:custom-components-changed", () => {
				loadCustomVueComponents()
			})
		}
	}

	async function deleteApp(appName: string, appTitle: string) {
		if (!appName) return
		const confirmed = await confirm(`Are you sure you want to delete the app <b>${appTitle}</b>?`)
		if (confirmed) {
			studioApps.delete.submit(appName, {
				onSuccess() {
					if (activeApp.value?.name === appName) {
						router.replace({ name: "Home" })
					}
					toast.success(`App "${appTitle}" deleted successfully`)
				},
				onError() {
					toast.error("An unexpected error occurred while deleting the app.")
				}
			})
		}
	}

	async function setAppPages(appName: string) {
		if (!appName) {
			return
		}
		studioPages.filters = { studio_app: appName }
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
		await setPageData(page)
		await codeStore.setPageWatchers(page)

		const blocks = JSON.parse(page.draft_blocks || page.blocks || "[]")
		if (blocks.length === 0) {
			pageBlocks.value = [getRootBlock()]
		} else {
			pageBlocks.value = [getBlockInstance(blocks[0])]
		}
		selectedPage.value = page.name

		const canvasStore = useCanvasStore()
		canvasStore.editingMode = "page"
		canvasStore.activeCanvas?.setRootBlock(pageBlocks.value[0])
		canvasStore.activeCanvas?.clearSelection()

		nextTick(() => {
			settingPage.value = false
		})
	}

	function savePage(rootBlock?: Block) {
		if (rootBlock) {
			pageBlocks.value = [rootBlock]
		} else {
			const canvasStore = useCanvasStore()
			if (canvasStore?.activeCanvas) {
				pageBlocks.value = [canvasStore.activeCanvas.getRootBlock()]
			}
		}
		const pageData = jsToJson(pageBlocks.value.map((block) => getBlockCopyWithoutParent(block)))

		const args = {
			name: selectedPage.value,
			draft_blocks: pageData,
			_skip_validate: true,
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
			{ name: activePage.value?.name, [key]: value, _skip_validate: true },
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
				await generateAppBuild()
				activePage.value = await fetchPage(selectedPage.value!)
				if (activeApp.value && activePage.value) {
					openPageInBrowser(activeApp.value, activePage.value)
				}
			})
	}

	async function unpublishPage() {
		if (!activePage.value) return
		const confirmed = await confirm(
			`Are you sure you want to unpublish the page <b>${activePage.value.page_title}</b>? It will no longer be publicly accessible.`,
		)
		if (!confirmed) {
			return
		}
		return studioPages.runDocMethod.submit(
			{
				name: selectedPage.value,
				method: "unpublish",
			},
			{
				onSuccess() {
					activePage.value!.published = 0
					setAppPages(activeApp.value!.name)
					toast.success("Page unpublished")
				},
				onError(error: any) {
					toast.error("Failed to unpublish the page", {
						description: error.messages.join(", "),
					})
				},
			}
		)
	}

	async function publishApp() {
		if (!activeApp.value) return
		return studioApps.runDocMethod.submit(
			{
				name: activeApp.value.name,
				method: "publish_app",
			},
			{
				async onSuccess(data: any) {
					activePage.value = await fetchPage(selectedPage.value!)
					setAppPages(activeApp.value!.name)
					openPageInBrowser(activeApp.value!, activePage.value!)
					toast.success(`App published successfully (${data?.message?.published_pages} pages)`)
				},
				onError(error: any) {
					toast.error("Failed to publish the app", {
						description: error?.messages?.join(", "),
					})
				},
			},
		)
	}

	async function unpublishApp() {
		if (!activeApp.value) return
		const confirmed = await confirm(
			`Are you sure you want to unpublish the app <b>${activeApp.value.app_name}</b>? It will no longer be publicly accessible.`,
		)
		if (!confirmed) {
			return
		}
		return studioApps.runDocMethod.submit(
			{
				name: activeApp.value.name,
				method: "unpublish_app",
			},
			{
				onSuccess() {
					setAppPages(activeApp.value!.name)
					toast.success("App unpublished")
				},
				onError(error: any) {
					toast.error("Failed to unpublish the app", {
						description: error?.messages?.join(", "),
					})
				},
			},
		)
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
				toast.warning("Skipped app build due to errors", {
					description: error?.messages?.join(", "),
					duration: Infinity,
				})
			},
		})
	}

	// styles
	const propertyFilter = ref<string | null>(null)

	// data
	const routeObject = computed(() => {
		if (!activePage.value) return ""

		const newRoute = toRaw(router.currentRoute.value)
		// Extract param names from active page's route (e.g., ["employee", "id"] from "/hr/:employee/:id")
		const paramNames = (activePage.value.route.match(/:\w+/g) || []).map(param => param.slice(1))
		newRoute.params = paramNames.reduce((params, name) => {
			params[name] = ""
			return params
		}, {} as Record<string, string>)

		return newRoute
	})

	const codeStore = useCodeStore()
	codeStore.setRouteObject(routeObject)

	async function setPageData(page: StudioPage) {
		await codeStore.setPageVariables(page)
		await codeStore.setPageResources(page, true)
	}

	const variableConfigs = computed<Record<string, Variable>>(() => {
		const configs: Record<string, Variable> = {}
		studioVariables.data.map((variable: Variable) => {
			configs[variable.variable_name] = {
				...variable,
				initial_value: getInitialVariableValue(variable),
			}
		})
		return configs
	})

	const variableOptions = computed(() => {
		const options: VariableOption[] = []

		function traverse(obj: any, path = "") {
			for (const key in obj) {
				const currentPath = path ? `${path}.${key}` : key
				const variableType = path === "" ? variableConfigs.value[key]?.variable_type : typeof obj[key]
				options.push({
					value: currentPath,
					label: currentPath,
					type: variableType
				})

				if (typeof obj[key] === "object" && obj[key] !== null) {
					// add nested properties
					traverse(obj[key], currentPath)
				}
			}
		}

		traverse(codeStore.variables)
		return options
	})

	return {
		// layout
		studioLayout,
		mode,
		componentContextMenu,
		// dialogs
		showSlotEditorDialog,
		showSearchBlock,
		// studio app
		activeApp,
		setApp,
		deleteApp,
		updateActiveApp,
		deleteAppPage,
		duplicateAppPage,
		appPages,
		setAppPages,
		getAppPageRoute,
		customVueComponents,
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
		unpublishPage,
		publishApp,
		unpublishApp,
		openPageInBrowser,
		routeObject,
		// app build
		generateAppBuild,
		// styles
		propertyFilter,
		// data/code
		variableConfigs,
		setPageData,
		variableOptions,
	}
})

export default useStudioStore
