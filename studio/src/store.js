import { ref, reactive, computed } from "vue"
import { defineStore } from "pinia"
import { createResource, createDocumentResource } from "frappe-ui"

import {
	getBlockInstance,
	getRootBlock,
	jsToJson,
	getBlockCopyWithoutParent,
	jsonToJs,
} from "@/utils/helpers"
import { studioPages } from "@/data/studioPages"

const useStore = defineStore("store", () => {
	const canvas = ref(null)
	const studioLayout = reactive({
		leftPanelWidth: 280,
		rightPanelWidth: 275,
		showLeftPanel: true,
		showRightPanel: true,
	})
	const activeBreakpoint = ref("desktop")
	const guides = reactive({
		showX: false,
		showY: false,
		x: 0,
		y: 0,
	})

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
	const activePage = ref(null)
	const pageBlocks = ref([])
	const selectedPage = ref(null)
	const savingPage = ref(false)
	const settingPage = ref(false)

	async function setPage(pageName) {
		const page = await fetchPage(pageName)
		activePage.value = page

		const blocks = jsonToJs(page.draft_blocks || page.blocks || "[]")
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

	async function findPageWithRoute(route) {
		let pageName = createResource({
			url: "studio.studio.doctype.studio_page.studio_page.find_page_with_route",
			method: "GET",
			params: { route: `studio-app/${route}` },
		})
		await pageName.fetch()
		pageName = pageName.data
		return fetchPage(pageName)
	}

	function savePage() {
		pageBlocks.value = [canvas.value.getRootBlock()]
		const pageData = jsToJson(pageBlocks.value.map((block) => getBlockCopyWithoutParent(block)))

		const args = {
			name: selectedPage.value,
			draft_blocks: pageData,
		}
		return studioPages.setValue.submit(args).finally(() => {
			savingPage.value = false
		})
	}

	async function publishPage() {
		return studioPages.runDocMethod
			.submit({
				name: selectedPage.value,
				method: "publish",
			})
			.then(async () => {
				activePage.value = await fetchPage(selectedPage.value)
				openPageInBrowser(activePage.value)
			})
	}

	function openPageInBrowser(page) {
		let route = page.route
		window.open(`/${route}`, "studio-preview")
	}

	return {
		canvas,
		studioLayout,
		activeBreakpoint,
		guides,
		hoveredBlock,
		hoveredBreakpoint,
		selectedBlockIds,
		selectedBlocks,
		selectBlock,
		pageBlocks,
		selectedPage,
		settingPage,
		savingPage,
		activePage,
		setPage,
		findPageWithRoute,
		fetchPage,
		savePage,
		publishPage,
		openPageInBrowser,
	}
})

export default useStore
