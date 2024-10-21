import { defineStore } from "pinia"
import { reactive, ref } from "vue"
import { studioPageResources } from "@/data/studioResources"
import { getNewResource } from "@/utils/helpers"

const useAppStore = defineStore("appStore", () => {
	const resources = reactive({})
	const localState = ref({})

	// TODO: deduplicate with studioStore later, if possible
	async function setPageResources(page) {
		studioPageResources.filters = { parent: page.name }
		await studioPageResources.reload()

		const resourcePromises = studioPageResources.data.map(async (resource) => {
			const newResource = await getNewResource(resource, localState.value)
			return {
				resource_name: resource.resource_name,
				value: newResource,
			}
		})

		const resolvedResources = await Promise.all(resourcePromises)

		resolvedResources.forEach((item) => {
			resources[item.resource_name] = item.value
		})
	}

	async function setLocalState(params) {
		localState.value = params
	}

	return {
		resources,
		setPageResources,
		localState,
		setLocalState,
	}
})

export default useAppStore
