import { ref, reactive, computed } from "vue"
import { defineStore } from "pinia"
import { createDocumentResource } from "frappe-ui"

import { getBlockInstance, getRootBlock } from "@/utils/helpers"

const useStore = defineStore("store", () => {
	const canvas = ref(null)
	const studioLayout = reactive({
		leftPanelWidth: 280,
		rightPanelWidth: 275,
		showLeftPanel: true,
		showRightPanel: true,
	})
	const activeBreakpoint = ref("desktop")

	// block hover & selection
	const hoveredBlock = ref(null)
	const hoveredBreakpoint = ref(null)
	const selectedBlockIds = ref([])
	const selectedBlocks = computed(() => {
		return (
			selectedBlockIds.value
				.map((id) => canvas.value.findBlock(id))
				// filter out missing blocks/null values
				.filter((b) => b)
		)
	})

	function selectBlock(block, e, multiSelect = false) {
		if (multiSelect) {
			selectedBlockIds.value.push(block.componentId)
		} else {
			selectedBlockIds.value.splice(0, selectedBlockIds.value.length, block.componentId)
		}
	}

	// studio pages
	const pageBlocks = ref([])
	const selectedPage = ref(null)

	async function setPage(pageName) {
		const page = await fetchPage(pageName)

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
		canvas,
		studioLayout,
		activeBreakpoint,
		hoveredBlock,
		hoveredBreakpoint,
		selectedBlockIds,
		selectedBlocks,
		selectBlock,
		pageBlocks,
		selectedPage,
		setPage,
		fetchPage,
	}
})

export default useStore
