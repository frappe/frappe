import { ref, reactive, computed, nextTick } from "vue"
import { defineStore } from "pinia"
import { createResource, createListResource, createDocumentResource } from "frappe-ui"

import {
	getBlockInstance,
	getRootBlock,
	jsToJson,
	getBlockCopyWithoutParent,
	jsonToJs,
	// page
	fetchPage,
} from "@/utils/helpers"
import { studioPages } from "@/data/studioPages"
import { studioPageResources } from "@/data/studioResources"

const useStore = defineStore("store", () => {
	const canvas = ref(null)
	const studioLayout = reactive({
		leftPanelWidth: 300,
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
		settingPage.value = true
		const page = await fetchPage(pageName)
		activePage.value = page

		const blocks = jsonToJs(page.draft_blocks || page.blocks || "[]")
		if (blocks.length === 0) {
			pageBlocks.value = [getRootBlock()]
		} else {
			pageBlocks.value = [getBlockInstance(blocks[0])]
		}
		selectedPage.value = page.name
		await setPageResources(page)
		nextTick(() => {
			settingPage.value = false
		})
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

	function updateActivePage(key, value) {
		if (!activePage.value) {
			return
		}
		return studioPages.setValue.submit(
			{ name: activePage.value.name, [key]: value },
			{
				onSuccess() {
					if (activePage.value) {
						activePage.value[key] = value
					}
				},
			},
		)
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

	// styles
	const stylePropertyFilter = ref(null)

	// data
	const resources = reactive({})

	async function setPageResources(page) {
		studioPageResources.filters = { parent: page.name }
		await studioPageResources.reload()

		studioPageResources.data.map((resource) => {
			resources[resource.resource_name] = getNewResource(resource)
		})
	}

	function getNewResource(resource) {
		const fields = JSON.parse(resource.fields || "[]")
		switch (resource.resource_type) {
			case "Document Resource":
				return createDocumentResource({
					doctype: resource.document_type,
					name: resource.document_name,
					auto: true,
				})
			case "List Resource":
				return createListResource({
					doctype: resource.document_type,
					fields: fields.length ? fields : "*",
					auto: true,
				})
			case "API Resource":
				return createResource({
					url: resource.url,
					method: resource.method,
					auto: true,
				})
		}
	}

	return {
		// layout
		canvas,
		studioLayout,
		activeBreakpoint,
		guides,
		// block hover & selection
		hoveredBlock,
		hoveredBreakpoint,
		selectedBlockIds,
		selectedBlocks,
		selectBlock,
		pageBlocks,
		// studio pages
		selectedPage,
		settingPage,
		savingPage,
		activePage,
		setPage,
		savePage,
		updateActivePage,
		publishPage,
		openPageInBrowser,
		// styles
		stylePropertyFilter,
		// data
		resources,
		setPageResources,
	}
})

export default useStore
