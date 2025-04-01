import { defineStore } from "pinia"
import { ref, watch, type WatchStopHandle } from "vue"
import { studioPageResources } from "@/data/studioResources"
import { studioVariables } from "@/data/studioVariables"
import { studioWatchers } from "@/data/studioWatchers"
import { getInitialVariableValue, getNewResource, executeUserScript } from "@/utils/helpers"

import type { Resource } from "@/types/Studio/StudioResource"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { Variable } from "@/types/Studio/StudioPageVariable"
import type { StudioPageWatcher } from "@/types/Studio/StudioPageWatcher"

const useAppStore = defineStore("appStore", () => {
	const resources = ref<Record<string, Resource>>({})
	const variables = ref<Record<string, any>>({})
	const localState = ref({})
	const activeWatchers = ref<Record<string, WatchStopHandle>>({})

	async function setPageData(page: StudioPage) {
		await setPageResources(page)
		await setPageVariables(page)
	}

	// TODO: deduplicate with studioStore later, if possible
	async function setPageResources(page: StudioPage) {
		studioPageResources.filters = { parent: page.name }
		await studioPageResources.reload()

		const resourcePromises = studioPageResources.data.map(async (resource: Resource) => {
			const newResource = await getNewResource(resource, localState.value)
			return {
				resource_name: resource.resource_name,
				value: newResource,
			}
		})

		const resolvedResources = await Promise.all(resourcePromises)

		resolvedResources.forEach((item) => {
			resources.value[item.resource_name] = item.value
		})
	}

	async function setPageVariables(page: StudioPage) {
		studioVariables.filters = { parent: page.name }
		await studioVariables.reload()

		studioVariables.data.map((variable: Variable) => {
			variables.value[variable.variable_name] = getInitialVariableValue(variable)
		})
	}

	async function setLocalState(params: object) {
		localState.value = params
	}

	async function setPageWatchers(page: StudioPage) {
		cleanupWatchers()
		studioWatchers.filters = { parent: page.name }
		await studioWatchers.reload()

		studioWatchers.data.map((watcher: StudioPageWatcher) => {
			setupWatcher(watcher)
		})
	}

	function setupWatcher(watcher: StudioPageWatcher) {
		const isDeep = typeof variables.value[watcher.source] === "object"
		const watcherFn = watch(
			() => variables.value[watcher.source],
			() => {
				executeUserScript(watcher.script, variables.value, resources.value)
			},
			{ deep: isDeep, immediate: watcher.immediate }
		)
		activeWatchers.value[watcher.name || watcher.source] = watcherFn
	}

	function cleanupWatchers() {
		Object.values(activeWatchers.value).forEach(stop => stop())
		activeWatchers.value = {}
	}

	return {
		setPageData,
		resources,
		setPageResources,
		variables,
		setPageVariables,
		localState,
		setLocalState,
		setPageWatchers,
	}
})

export default useAppStore
