import { ref, reactive } from "vue"
import { defineStore } from "pinia"
import { createDocumentResource } from "frappe-ui"

import { getBlockInstance, getRootBlock } from "@/utils/helpers"

const useStore = defineStore("store", () => {
	const pageBlocks = ref([])
	const selectedPage = ref(null)

	async function setPage(pageName) {
		const page = await fetchPage(pageName)
		console.log(page.blocks)

		const blocks = JSON.parse(page.blocks || "[]")
		if (blocks.length === 0) {
			pageBlocks.value = [getRootBlock()]
		} else {
			pageBlocks.value = [getBlockInstance(blocks[0])]
		}
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

	return {
		pageBlocks,
		setPage,
		fetchPage,
	}
})

export default useStore
