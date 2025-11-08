import { defineStore } from "pinia"
import { ref, watch, type WatchStopHandle, ComputedRef } from "vue"
import { studioPageResources } from "@/data/studioResources"
import { studioVariables } from "@/data/studioVariables"
import { studioWatchers } from "@/data/studioWatchers"
import { getInitialVariableValue } from "@/utils/helpers"
import { getNewResource, executeUserScript } from "@/utils/code"

import type { Resource } from "@/types/Studio/StudioResource"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { Variable } from "@/types/Studio/StudioPageVariable"
import type { StudioPageWatcher } from "@/types/Studio/StudioPageWatcher"

const useCodeStore = defineStore("codeStore", () => {
	const resources = ref<Record<string, Resource>>({})
	const variables = ref<Record<string, any>>({})
	const activeWatchers = ref<Record<string, WatchStopHandle>>({})

	async function setPageResources(
		page: StudioPage,
		routeObject: ComputedRef,
		setResourceConfig: boolean = false,
	) {
		studioPageResources.filters = { parent: page.name }
		await studioPageResources.reload()

		const resourcePromises = studioPageResources.data.map(async (resource: Resource) => {
			const newResource = await getNewResource(resource, {
				...variables.value,
				route: routeObject.value,
			})
			return {
				resource_name: resource.resource_name,
				value: newResource,
			}
		})

		const resolvedResources = await Promise.all(resourcePromises)

		resolvedResources.forEach((item) => {
			resources.value[item.resource_name] = item.value
			if (setResourceConfig) {
				if (!item.value) return
				resources.value[item.resource_name].resource_id = item.resource_id
				resources.value[item.resource_name].resource_type = item.resource_type
			}
		})
	}

	async function setPageVariables(page: StudioPage) {
		studioVariables.filters = { parent: page.name }
		await studioVariables.reload()

		studioVariables.data.map((variable: Variable) => {
			variables.value[variable.variable_name] = getInitialVariableValue(variable)
		})
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
		resources,
		setPageResources,
		variables,
		setPageVariables,
		setPageWatchers,
	}
})

export default useCodeStore
