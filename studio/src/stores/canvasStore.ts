import { defineStore } from "pinia"
import { ref, reactive, computed, nextTick } from "vue"
import type Block from "@/utils/block"
import { getBlockCopy, getBlockInstance } from "@/utils/serializer"
import { confirm } from "@/utils/helpers"

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

	// dialogs
	const showHTMLDialog = ref(false)
	const editableBlock = ref<Block | null>(null)

	function editHTML(block: Block) {
		editableBlock.value = block
		nextTick(() => {
			showHTMLDialog.value = true
		})
	}

	function closeHTMLDialog() {
		showHTMLDialog.value = false
		editableBlock.value = null
	}

	const showCodeDialog = ref(false)
	const editableCode = ref({
		propName: "" as string,
		code: "" as string,
	})
	function editCode(block: Block, propName: string, code: string) {
		editableBlock.value = block
		editableCode.value.code = code
		editableCode.value.propName = propName
		nextTick(() => {
			showCodeDialog.value = true
		})
	}

	const isAIStreaming = ref(false)

	// drag & drop
	const isDragging = ref(false)
	const layerDraggingOverBlock = ref<string | null>(null)
	const layerDraggingOverSlot = ref<string | null>(null)
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
	type FragmentData = {
		block: Block
		saveAction: (block: Block) => void | Promise<void>
		saveActionLabel: string
		fragmentName: string
		fragmentId: string
		cancelAction: Function | null
		mode: EditingMode
		dirty?: boolean
	}

	const editingMode = ref<EditingMode>("page")
	const fragmentStack = ref<FragmentData[]>([])
	const fragmentData = computed(() => {
		return (
			fragmentStack.value[fragmentStack.value.length - 1] || {
				block: null,
				saveAction: null,
				saveActionLabel: null,
				fragmentName: null,
				fragmentId: null,
				cancelAction: null,
				mode: "page" as EditingMode,
			}
		)
	})

	const showFragmentCanvas = computed(() => {
		return Boolean(editingMode.value === "fragment" || (editingMode.value === "component" && fragmentData.value?.block))
	})

	// the fragment canvas always renders one primary surface inline: the overlay root itself
	const primaryOverlayId = computed(() => {
		const rootBlock = fragmentData.value.block
		if (!rootBlock) return null
		if (rootBlock.isOverlayNode()) return rootBlock.componentId
		if (rootBlock.hasNonOverlayContent()) return null
		return rootBlock.findFirstOverlayNode()?.componentId || null
	})

	async function editOnCanvas(
		block: Block,
		saveAction: (block: Block) => void,
		saveActionLabel: string = "Save",
		fragmentName?: string,
		fragmentId?: string,
		mode: EditingMode = "fragment",
		cancelAction?: Function,
	) {
		syncActiveFragmentBlock()
		const blockCopy = getBlockCopy(block, true)
		fragmentStack.value.push({
			block: blockCopy,
			saveAction,
			saveActionLabel,
			fragmentName: fragmentName || block.componentName,
			fragmentId: fragmentId || block.componentId,
			cancelAction: cancelAction || null,
			mode,
		})
		editingMode.value = mode
	}

	// the fragment canvas edits its own copy of the tree — sync it back into the
	// active stack entry before drilling down, so edits survive the canvas remount
	function syncActiveFragmentBlock() {
		const activeFragment = fragmentStack.value[fragmentStack.value.length - 1]
		if (activeFragment && activeCanvas.value) {
			activeFragment.block = activeCanvas.value.getRootBlock()
			activeFragment.dirty = isActiveFragmentDirty.value
		}
	}

	function popFragment(cancelled: boolean = false) {
		const exitedFragment = fragmentStack.value.pop()
		if (cancelled && exitedFragment?.cancelAction) {
			exitedFragment.cancelAction()
		}
		activeCanvas.value?.clearSelection()
		const activeFragment = fragmentStack.value[fragmentStack.value.length - 1]
		if (!cancelled && activeFragment) {
			// a nested save wrote into this fragment's tree — it now has unsaved changes
			activeFragment.dirty = true
		}
		editingMode.value = activeFragment ? activeFragment.mode : "page"
	}

	function markActiveFragmentClean() {
		const activeFragment = fragmentStack.value[fragmentStack.value.length - 1]
		if (activeFragment) {
			activeFragment.dirty = false
		}
		activeCanvas.value?.history?.markClean()
	}

	const isActiveFragmentDirty = computed(() => {
		if (editingMode.value === "page") return false
		return Boolean(fragmentData.value.dirty || activeCanvas.value?.history?.isDirty())
	})

	async function confirmDiscardFragments(fromIndex: number): Promise<boolean> {
		const poppedFragments = fragmentStack.value.slice(fromIndex)
		const dirtyNames = poppedFragments.filter((fragment) => fragment.dirty).map((f) => f.fragmentName)
		if (isActiveFragmentDirty.value && !dirtyNames.includes(fragmentData.value.fragmentName)) {
			dirtyNames.push(fragmentData.value.fragmentName)
		}
		if (!dirtyNames.length) return true
		return await confirm(`Discard unsaved changes in ${dirtyNames.join(", ")}?`)
	}

	async function exitFragmentMode(e?: Event) {
		if (editingMode.value === "page") return
		e?.preventDefault()
		if (await confirmDiscardFragments(fragmentStack.value.length - 1)) {
			popFragment(true)
		}
	}

	async function popToFragment(index: number) {
		if (fragmentStack.value.length <= index + 1) return
		if (!(await confirmDiscardFragments(index + 1))) return
		while (fragmentStack.value.length > index + 1) {
			popFragment(true)
		}
	}

	async function exitAllFragments() {
		if (!fragmentStack.value.length) return
		if (!(await confirmDiscardFragments(0))) return
		while (fragmentStack.value.length) {
			popFragment(true)
		}
	}

	function resetFragments() {
		fragmentStack.value = []
		editingMode.value = "page"
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
		// dialogs
		showHTMLDialog,
		editableBlock,
		editHTML,
		closeHTMLDialog,
		showCodeDialog,
		editCode,
		editableCode,
		// ai streaming
		isAIStreaming,
		// drag & drop
		dropTarget,
		isDragging,
		layerDraggingOverBlock,
		layerDraggingOverSlot,
		handleDragStart,
		handleDragEnd,
		// fragment mode
		editingMode,
		showFragmentCanvas,
		fragmentStack,
		fragmentData,
		primaryOverlayId,
		isActiveFragmentDirty,
		markActiveFragmentClean,
		editOnCanvas,
		exitFragmentMode,
		popFragment,
		popToFragment,
		exitAllFragments,
		resetFragments,
		// blocks
		pushBlocks,
	}
})

export default useCanvasStore