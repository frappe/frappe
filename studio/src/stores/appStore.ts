import { defineStore } from "pinia"
import { reactive, ref } from "vue"
import { studioPageResources } from "@/data/studioResources"
import { studioVariables } from "@/data/studioVariables"
import { getInitialVariableValue, getNewResource } from "@/utils/helpers"

import type { Resource } from "@/types/Studio/StudioResource"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { Variable } from "@/types/Studio/StudioPageVariable"

const useAppStore = defineStore("appStore", () => {
	const resources = ref<Record<string, Resource>>({})
	const variables = ref<Record<string, any>>({})
	const localState = ref({})

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

	return {
		setPageData,
		resources,
		setPageResources,
		variables,
		setPageVariables,
		localState,
		setLocalState,
	}
})

export default useAppStore
