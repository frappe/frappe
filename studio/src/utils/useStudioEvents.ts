import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { useEventListener } from "@vueuse/core"
import blockController from "@/utils/blockController"
import { isTargetEditable, numberToPx, isHTML } from "@/utils/helpers"
import { getComponentBlock } from "@/utils/serializer"
import { copyBlocks, copySelectedBlocks, pasteBlocks, pasteDataSource } from "@/utils/blockCopyPaste"
import Block from "@/utils/block"
import type { BlockOptions } from "@/types"
import { toast, useKeyboardShortcut } from "frappe-ui"
import { commandShortcuts } from "@/components/Commands"

const store = useStudioStore()
const canvasStore = useCanvasStore()

export function useStudioEvents(saveFragmentMode: () => void) {
	useEventListener(document, "copy", (e) => {
		if (isTargetEditable(e) || window.getSelection()?.toString()) return
		copyBlocks(e)
	})

	useEventListener(document, "cut", (e) => {
		if (isTargetEditable(e)) return
		copySelectedBlocks(e)
		if (canvasStore.activeCanvas?.selectedBlocks.length) {
			for (const block of canvasStore.activeCanvas?.selectedBlocks) {
				canvasStore.activeCanvas?.removeBlock(block, true)
			}
			clearSelection()
		}
	})

	useEventListener(document, "paste", async (e) => {
		if (isTargetEditable(e)) return
		e.stopPropagation()

		if (pasteBlocks(e) || pasteDataSource(e)) return

		let text = e.clipboardData?.getData("text/plain") as string
		if (!text) {
			return
		}

		if (isHTML(text)) {
			e.preventDefault()
			pasteHTML(text)
		}
	})

	useEventListener(document, "contextmenu", async (e) => {
		const target =
			<HTMLElement | null>(e.target as HTMLElement)?.closest("[data-component-layer-id]") ||
			(e.target as HTMLElement)?.closest("[data-component-id]:not(.__studio_component_child__)")
		if (target) {
			const blockId = target.dataset.componentLayerId || target.dataset.componentId
			const block = canvasStore.activeCanvas?.findBlock(blockId as string)
			if (block) {
				const alreadyInSelection = canvasStore.activeCanvas?.selectedBlockIds.has(block.componentId)
				if (!(blockController.multipleBlocksSelected() && alreadyInSelection)) {
					canvasStore.activeCanvas?.selectBlock(block, null)
				}

				const slotName = target.dataset.slotName
				if (slotName) {
					const slot = block.getSlot(slotName)
					if (slot) {
						canvasStore.activeCanvas?.selectSlot(slot)
					}
				}

				store.componentContextMenu?.showContextMenu(e, block)
			}
		}
	})

	// a command that declares keys owns its binding; what is left needs the
	// keyboard event or the fragment save, so it stays a plain shortcut
	const shortcuts = [
		...commandShortcuts(),
		{
			combo: "Mod+S",
			description: "Save Component",
			group: "General",
			allowInInput: true,
			// the page autosaves - in page mode this just swallows the browser's save dialog
			enabled: () => Boolean(store.selectedPage),
			handler: () => {
				if (canvasStore.editingMode !== "page") {
					saveFragmentMode()
				}
			},
		},
		{
			combo: "Escape",
			description: "Exit Component Editing",
			group: "General",
			preventDefault: false,
			// a drag handles its own Escape: it cancels the drag, not the fragment
			enabled: () => canvasStore.editingMode !== "page" && !canvasStore.isDragging,
			handler: (e: KeyboardEvent) => {
				// Escape in the context menu only closes the menu
				if ((e.target as Element | null)?.closest?.('[role="menu"]')) return
				// after this keypress: a discard confirmation mounted now would hear the same
				// Escape on window and close before it can be answered
				setTimeout(() => canvasStore.exitFragmentMode())
			},
		},
		...(["Backspace", "Delete"] as const).map((combo) => ({
			combo,
			description: "Delete Selected Blocks",
			group: "Edit",
			handler: deleteSelection,
		})),
	]
	// combos are plain strings here: Studio's frappe-ui import is untyped (src/lib.d.ts)
	useKeyboardShortcut(shortcuts as Parameters<typeof useKeyboardShortcut>[0])
}

const deleteSelection = (e: KeyboardEvent) => {
	// a selected slot takes precedence over its (also-selected) parent block
	const selectedSlot = canvasStore.activeCanvas?.selectedSlot
	if (selectedSlot) {
		const parent = canvasStore.activeCanvas?.findBlock(selectedSlot.parentBlockId)
		parent?.removeSlot(selectedSlot.slotName)
		e.stopPropagation()
		return
	}

	if (blockController.isAnyBlockSelected()) {
		for (const block of blockController.getSelectedBlocks()) {
			canvasStore.activeCanvas?.removeBlock(block)
		}
		clearSelection()
		e.stopPropagation()
	}
}

const clearSelection = () => {
	blockController.clearSelection()
	if (document.activeElement instanceof HTMLElement) {
		document.activeElement.blur()
	}
}

const pasteHTML = (text: string) => {
	if (blockController.isHTML()) {
		const selectedBlocks = blockController.getSelectedBlocks()
		selectedBlocks[0].setProp("html", text)
	} else {
		let block = null as unknown as Block | BlockOptions
		block = getComponentBlock("HTML")

		if (text.startsWith("<svg")) {
			if (text.includes("<image")) {
				toast.warning("Warning", {
					description: "SVG with inlined image in it is not supported.",
				})
				return
			}
			const dom = new DOMParser().parseFromString(text, "text/html")
			const svg = dom.body.querySelector("svg") as SVGElement
			const width = svg.getAttribute("width") || "100"
			const height = svg.getAttribute("height") || "100"
			if (width && block.baseStyles) {
				block.baseStyles.width = numberToPx(parseInt(width))
				svg.removeAttribute("width")
			}
			if (height && block.baseStyles) {
				block.baseStyles.height = numberToPx(parseInt(height))
				svg.removeAttribute("height")
			}
			text = svg.outerHTML
		}

		block.setProp("html", text)

		const selectedBlocks = blockController.getSelectedBlocks()
		let parentBlock = selectedBlocks.length ? selectedBlocks[0] : null

		while (parentBlock && !parentBlock.canHaveChildren()) {
			parentBlock = parentBlock.getParentBlock()
		}

		if (parentBlock) {
			parentBlock.addChild(block)
		} else {
			canvasStore.pushBlocks([block])
		}
	}
}
