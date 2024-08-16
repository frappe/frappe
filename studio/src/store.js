import { ref, reactive } from "vue"
import { defineStore } from "pinia"
import { createDocumentResource } from "frappe-ui"

import { getBlockCopy } from "@/utils/helpers"
import components from "@/data/components"

const useStore = defineStore("store", () => {
	const pageBlocks = ref([])
	const selectedPage = ref(null)

	async function setPage(pageName) {
		const page = await fetchPage(pageName)
		pageBlocks.value = [getBlockCopy(page.blocks)]
		selectedPage.value = page.name
	}

	async function fetchPage(pageName) {
		const pageResource = createDocumentResource({
			doctype: "Studio Page",
			name: pageName,
		})
		await pageResource.get.promise
		return pageResource.doc
	}

	function getRootBlock() {
		return reactive({
			componentName: "div",
			componentId: "root",
			children: [],
		})
	}

	function getComponentBlock(componentName) {
		const component = components.get(componentName)
		return reactive({
			componentName: component.name,
			componentId: `${component.name}-${Math.random().toString(36).substring(2, 9)}`,
			children: [],
		})
	}

	return {
		pageBlocks,
		setPage,
		fetchPage,
		getRootBlock,
		getComponentBlock,
	}
})

export default useStore
