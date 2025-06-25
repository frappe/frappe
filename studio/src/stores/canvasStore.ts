import { defineStore } from "pinia"
import { ref, reactive } from "vue"
import type Block from "@/utils/block"
import { getBlockCopy, getBlockInstance } from "@/utils/helpers"

import type StudioCanvas from "@/components/StudioCanvas.vue"
import type { EditingMode, BlockOptions } from "@/types"

const useCanvasStore = defineStore("canvasStore", () => {
	const activeCanvas = ref<InstanceType<typeof StudioCanvas> | null>(null)
	const guides = reactive({
		showX: false,
		showY: false,
		x: 0,
		y: 0,
	})

	// drag & drop
	const isDragging = ref(false)
	const dropTarget = reactive({
		x: null as number | null,
		y: null as number | null,
		placeholder: null as HTMLElement | null,
		parentComponent: null as Block | null,
		index: null as number | null,
		slotName: null as string | null,
	})

	const handleDragStart = (ev: DragEvent, componentName: string) => {
		if (ev.target && ev.dataTransfer) {
			isDragging.value = true
			const ghostScale = activeCanvas.value?.canvasProps.scale
			const ghostElement = (ev.target as HTMLElement).cloneNode(true) as HTMLElement
			ghostElement.id = "ghost"
			ghostElement.style.position = "fixed"
			ghostElement.style.transform = `scale(${ghostScale || 1})`
			ghostElement.style.pointerEvents = "none"
			ghostElement.style.zIndex = "999999"
			document.body.appendChild(ghostElement)

			// Set the scaled drag image
			ev.dataTransfer.setDragImage(ghostElement, 0, 0)
			// Clean up the ghost element
			setTimeout(() => {
				document.body.removeChild(ghostElement)
			}, 0)
			ev.dataTransfer.setData("componentName", componentName)

			let element = document.createElement("div")
			element.id = "placeholder"

			const root = document.querySelector(".__studio_component__[data-component-id='root']")
			if (root) {
				dropTarget.placeholder = root.appendChild(element)
			}
		}
	}

	const handleDragEnd = () => {
		const placeholder = document.getElementById("placeholder")
		if (placeholder) {
			placeholder.remove()
		}

		dropTarget.x = null
		dropTarget.y = null
		dropTarget.placeholder = null
		dropTarget.parentComponent = null
		dropTarget.index = null
		dropTarget.slotName = null

		isDragging.value = false
	}

	// fragment mode
	const editingMode = ref<EditingMode>("page")
	const fragmentData = ref({
		block: <Block | null>null,
		saveAction: <Function | null>null,
		saveActionLabel: <string | null>null,
		fragmentName: <string | null>null,
		fragmentId: <string | null>null,
	})

	async function editOnCanvas(
		block: Block,
		saveAction: (block: Block) => void,
		saveActionLabel: string = "Save",
		fragmentName?: string,
		fragmentId?: string
	) {
		const blockCopy = getBlockCopy(block, true)
		fragmentData.value = {
			block: blockCopy,
			saveAction,
			saveActionLabel,
			fragmentName: fragmentName || block.componentName,
			fragmentId: fragmentId || block.componentId
		}
		editingMode.value = "fragment"
	}

	async function exitFragmentMode(e?: Event) {
		if (editingMode.value === "page") return
		e?.preventDefault()

		activeCanvas.value?.clearSelection()
		editingMode.value = "page"
		fragmentData.value = {
			block: null,
			saveAction: null,
			saveActionLabel: null,
			fragmentName: null,
			fragmentId: null,
		}
	}

	function pushBlocks(blocks: BlockOptions[]) {
		let parent = activeCanvas.value?.getRootBlock()
		let firstBlock = getBlockInstance(blocks[0])

		if (editingMode.value === "page" && firstBlock.isRoot() && activeCanvas.value?.rootComponent) {
			activeCanvas.value.setRootBlock(firstBlock)
		} else {
			for (let block of blocks) {
				parent?.addChild(block)
			}
		}
	}

	return {
		// layout
		activeCanvas,
		guides,
		// drag & drop
		dropTarget,
		isDragging,
		handleDragStart,
		handleDragEnd,
		// fragment mode
		editingMode,
		fragmentData,
		editOnCanvas,
		exitFragmentMode,
		// blocks
		pushBlocks,
	}
})

export default useCanvasStore