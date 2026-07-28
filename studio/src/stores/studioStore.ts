import { ref, nextTick, computed, toRaw, readonly } from "vue"
import { useDebounceFn, useStorage } from "@vueuse/core"
import router from "@/router/studio_router"
import { defineStore } from "pinia"

import {
	fetchApp,
	fetchPage,
	confirm,
	getInitialVariableValue,
	getRouteVariables,
} from "@/utils/helpers"
import { getBlockInstance, getRootBlock, getBlockCopyWithoutParent, jsToJson } from "@/utils/serializer"
import { studioPages } from "@/data/studioPages"
import { studioApps } from "@/data/studioApps"
import { studioVariables } from "@/data/studioVariables"

import Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import useCodeStore from "@/stores/codeStore"
import { reloadCustomVueComponents } from "@/globals"
import {
	registerStudioPageScripts,
	unregisterStudioPageScripts,
} from "@/data/studioPageScripts"
import { registerCustomComponentPaths } from "@/utils/components"
import type { CustomVueComponentMeta } from "@/types/vue"

import type { StudioApp } from "@/types/Studio/StudioApp"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { LeftPanelOptions, RightPanelOptions, leftPanelComponentTabOptions, StudioMode } from "@/types"
import ComponentContextMenu from "@/components/ComponentContextMenu.vue"
import type { Variable, VariableOption } from "@/types/Studio/StudioPageVariable"
import { toast, dialog } from "frappe-ui"
import { createResource, call } from "frappe-ui"

const useStudioStore = defineStore("store", () => {
	const studioLayout = useStorage(
		"studioLayout",
		{
			leftPanelWidth: 338,
			rightPanelWidth: 275,
			showLeftPanel: true,
			showRightPanel: true,
			leftPanelActiveTab: <LeftPanelOptions>"Add Component",
			leftPanelComponentTab: <leftPanelComponentTabOptions>"Standard",
			rightPanelActiveTab: <RightPanelOptions>"Properties",
		},
		localStorage,
		{ mergeDefaults: true },
	)
	const mode = ref<StudioMode>("select")
	const componentContextMenu = ref<InstanceType<typeof ComponentContextMenu> | null>(null)

	// dialogs
	const showSearchBlock = ref(false)
	const showStudioSettingsDialog = ref(false)
	const showPageOptions = ref(false)

	// studio apps
	const activeApp = ref<StudioApp | null>(null)
	const appPages = computed<Record<string, StudioPage>>(() => {
		const pages: Record<string, StudioPage> = {}
		studioPages.data.map((page: StudioPage) => {
			pages[page.name] = page
		})
		return pages
	})
	const customVueComponents = ref<CustomVueComponentMeta[]>([])

	// cross-panel navigation
	const selectedVueFile = ref<string | null>(null)
	const selectedVueComponent = ref<string | null>(null)

	function navigateToCodeFile(studioFilePath: string) {
		studioLayout.value.leftPanelActiveTab = "Code"
		studioLayout.value.showLeftPanel = true
		selectedVueFile.value = studioFilePath
	}

	function navigateToVueComponent(componentName: string) {
		studioLayout.value.leftPanelActiveTab = "Add Component"
		studioLayout.value.leftPanelComponentTab = "Custom"
		studioLayout.value.showLeftPanel = true
		selectedVueComponent.value = componentName
	}

	async function setApp(appName: string) {
		const appDoc = await fetchApp(appName)
		if (!appDoc) return
		activeApp.value = appDoc
		await setAppPages(appName)
		await setCustomComponents()
		await setupPageScripts()
	}

	async function deleteApp(appName: string, appTitle: string) {
		if (!appName) return
		const confirmed = await confirm(`Are you sure you want to delete the app "${appTitle}"?`)
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

		const confirmed = await confirm(`Are you sure you want to delete the page "${page.page_title}"?`)
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
	// set when a save is rejected because the page moved on in the DB (a disk sync or an AI edit)
	// after the editor loaded it. Autosave pauses until the user refreshes to the latest version.
	const pageConflict = ref(false)

	// design-time test values for dynamic route variables (e.g. { category: "tech" }), persists in localStorage
	const routeVariables = ref<Record<string, string>>({})

	async function setPage(pageName: string) {
		settingPage.value = true
		pageConflict.value = false
		const page = await fetchPage(pageName)
		if (!page) {
			settingPage.value = false
			return
		}
		activePage.value = page
		loadRouteVariables(page)
		await setPageData(page)
		await codeStore.setPageScript(page, Boolean(page.is_standard))

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
		const savedPage = selectedPage.value

		return studioPages.runDocMethod
			.submit({
				name: savedPage,
				method: "save_draft",
				draft_blocks: pageData,
				known_modified: activePage.value?.modified,
			})
			.then((response: any) => {
				// a save that resolves after the user switched pages must not stamp this page's
				// timestamp/draft marker onto the newly opened one
				if (activePage.value?.name !== savedPage) return
				syncPageModified(response)
				// track that the page now has unpublished changes (drives the "Revert Changes" option)
				activePage.value.draft_blocks = pageData
			})
			.catch(handlePageWriteConflict)
			.finally(() => {
				savingPage.value = false
			})
	}

	function syncPageModified(response: any) {
		const modified = response?.docs?.[0]?.modified ?? response?.modified ?? response?.message
		if (activePage.value && modified) activePage.value.modified = modified
	}

	async function refreshActivePageModified() {
		const pageName = activePage.value?.name
		if (!pageName) return
		const page = await call("frappe.client.get_value", {
			doctype: "Studio Page",
			filters: pageName,
			fieldname: "modified",
		})
		if (activePage.value?.name === pageName) syncPageModified(page)
	}

	function handlePageWriteConflict(error: any) {
		if (error?.exc_type === "TimestampMismatchError") {
			if (pageConflict.value) return
			pageConflict.value = true
			showPageOptions.value = false
			dialog.confirm({
				title: "Page changed outside the editor",
				message:
					"This page was updated after you opened it. Refresh to load the latest version - your unsaved canvas changes will be replaced.",
				confirmLabel: "Refresh",
				theme: "yellow",
				onConfirm: () => selectedPage.value && setPage(selectedPage.value),
			})
		}
		else throw error
	}

	function updateActivePage(key: string, value: string | number) {
		return studioPages.runDocMethod
			.submit({
				name: activePage.value?.name,
				method: "save_page_field",
				fieldname: key,
				value: value,
				known_modified: activePage.value?.modified,
			})
			.then((response: any) => {
				activePage.value![key] = value
				syncPageModified(response)
			})
			.catch(handlePageWriteConflict)
	}

	// A server tool (AI) wrote the page script straight to the DB / code file, so re-fetch the
	// page and re-run setup() on the canvas. (Standard pages update only after their app rebuilds.)
	async function reloadActivePageScript() {
		if (!activePage.value) return
		const page = await fetchPage(activePage.value.name)
		if (!page) return
		activePage.value = page
		await codeStore.setPageScript(page, Boolean(page.is_standard))
	}

	async function publishPage() {
		if (!selectedPage.value) return

		return studioPages.runDocMethod
			.submit(
				{
					name: selectedPage.value,
					method: "publish",
					known_modified: activePage.value?.modified,
				},
				{
					onError(error: any) {
						try {
							handlePageWriteConflict(error)
						} catch {
							toast.error("Failed to publish the page", {
								description: error.messages.join(", "),
								duration: Infinity,
								action: {
									label: "Edit Pages",
									onClick: () => {
										studioLayout.value.leftPanelActiveTab = "Pages"
									}
								}
							})
						}
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
			`Are you sure you want to unpublish the page "${activePage.value.page_title}"? It will no longer be publicly accessible.`,
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
				onSuccess(data: any) {
					activePage.value!.published = 0
					syncPageModified(data)
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

	function revertPage() {
		if (!activePage.value) return
		dialog.confirm({
			title: "Revert changes",
			message:
				"This will discard all changes made to the page since it was last published. Are you sure you want to continue?",
			confirmLabel: "Revert",
			theme: "yellow",
			onConfirm: async () => {
				try {
					const response = await studioPages.runDocMethod.submit({
						name: selectedPage.value,
						method: "revert",
						known_modified: activePage.value?.modified,
					})
					syncPageModified(response)
					await setPage(selectedPage.value!)
					toast.success("Changes reverted")
				} catch (error: any) {
					try {
						handlePageWriteConflict(error)
					} catch {
						toast.error("Failed to revert the changes", {
							description: error?.messages?.join(", "),
						})
					}
				}
			},
		})
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
		let route = `/${app.route}${resolveRouteVariables(page.route)}`
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

	// substitute test route variables set by the user into the dynamic route so preview opens the concrete URL,
	// e.g. "/notes/:id" + { id: "note-1" } -> "/notes/note-1" (unset params keep their placeholder)
	function resolveRouteVariables(route: string) {
		return getRouteVariables(route).reduce((resolved, name) => {
			const value = routeVariables.value[name]
			return value ? resolved.replace(`:${name}`, encodeURIComponent(value)) : resolved
		}, route)
	}

	// custom components
	async function setCustomComponents() {
		await loadCustomVueComponents()
		await registerCustomComponentPaths(customVueComponents.value)
	}

	async function loadCustomVueComponents() {
		const frappeApp = activeApp.value?.is_standard ? activeApp.value.frappe_app! : ""
		customVueComponents.value = await reloadCustomVueComponents(frappeApp)
	}

	// Register per-page code scripts (<page>.ts) for exported apps so the editor can load them.
	async function setupPageScripts() {
		unregisterStudioPageScripts()
		if (activeApp.value?.is_standard) {
			await registerStudioPageScripts(activeApp.value.frappe_app!)
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
		// Seed each dynamic param with its design-time test value (empty string when unset),
		// e.g. "/hr/:employee/:id" -> { employee, id } filled from routeVariables
		const paramNames = getRouteVariables(activePage.value.route)
		newRoute.params = paramNames.reduce((params, name) => {
			params[name] = routeVariables.value[name] ?? ""
			return params
		}, {} as Record<string, string>)

		return newRoute
	})

	// route variables on the active page that have no test value yet — used to nudge the user, since
	// unset variables render the page's empty state (no doc / no rows) which can look like a bug
	const areRouteVariablesSet = computed(() => {
		if (!activePage.value) return true
		return getRouteVariables(activePage.value.route).every((name) => !!routeVariables.value[name])
	})

	function loadRouteVariables(page: StudioPage) {
		const key = `${page.name}:routeVariables`
		try {
			const stored = localStorage.getItem(key)
			const parsed = stored ? JSON.parse(stored) : null
			routeVariables.value = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {}
		} catch (error) {
			console.error(`Failed to parse route variables for ${page.name}, resetting`, error)
			routeVariables.value = {}
			localStorage.removeItem(key)
		}
	}

	function setRouteVariable(name: string, value: string) {
		if (!activePage.value) return
		routeVariables.value[name] = value
		localStorage.setItem(
			`${activePage.value.name}:routeVariables`,
			JSON.stringify(routeVariables.value),
		)
		resetState()
	}

	const resetState = useDebounceFn(async () => {
		const page = activePage.value
		if (!page) return
		// re-resolve data sources with the new value, then re-run the page script so bindings that
		// derive from a resource (e.g. refs seeded from note.doc via a watcher) re-bind to the new doc.
		await codeStore.setPageResources(page, true)
		await codeStore.setPageScript(page, Boolean(page.is_standard))
	}, 300)

	const codeStore = useCodeStore()
	codeStore.setRouteObject(routeObject)
	codeStore.setRouterObject(readonly(router))

	// A page script (or a composable/util it imports) hot-updated. Re-run it in place when it's the
	// active page so new refs/functions and changed dependency code show up on the canvas, in the
	// value selectors and in completions — no reload. Non-active pages refresh lazily on navigation
	// (studioPageScripts caches the latest setup).
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

	const pageScriptBindingOptions = computed<VariableOption[]>(() => {
		return Object.entries(codeStore.pageScriptTemplateBindings).map(([key, value]) => ({
			value: key,
			label: key,
			type: typeof value,
		}))
	})

	return {
		// layout
		studioLayout,
		mode,
		componentContextMenu,
		// dialogs
		showSearchBlock,
		showStudioSettingsDialog,
		showPageOptions,
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
		// custom components
		setCustomComponents,
		loadCustomVueComponents,
		customVueComponents,
		// cross-panel navigation
		selectedVueFile,
		selectedVueComponent,
		navigateToCodeFile,
		navigateToVueComponent,
		// studio pages
		pageBlocks,
		selectedPage,
		settingPage,
		savingPage,
		pageConflict,
		activePage,
		setPage,
		savePage,
		updateActivePage,
		syncPageModified,
		refreshActivePageModified,
		reloadActivePageScript,
		publishPage,
		unpublishPage,
		revertPage,
		publishApp,
		unpublishApp,
		openPageInBrowser,
		routeObject,
		routeVariables,
		areRouteVariablesSet,
		setRouteVariable,
		// app build
		generateAppBuild,
		// styles
		propertyFilter,
		// data/code
		variableConfigs,
		setPageData,
		variableOptions,
		pageScriptBindingOptions,
	}
})

export default useStudioStore
