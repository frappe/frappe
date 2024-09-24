import { defineStore } from "pinia"
import { reactive } from "vue"
import { studioPageResources } from "@/data/studioResources"
import { getNewResource } from "@/utils/helpers"

const useAppStore = defineStore("appStore", () => {
	const resources = reactive({})

	// TODO: deduplicate with studioStore later, if possible
	async function setPageResources(page) {
		studioPageResources.filters = { parent: page.name }
		await studioPageResources.reload()

		studioPageResources.data.map((resource) => {
			resources[resource.resource_name] = getNewResource(resource)
		})
	}

	return {
		resources,
		setPageResources,
	}
})

export default useAppStore
