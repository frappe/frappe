import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { useEventListener } from "@vueuse/core"
import blockController from "@/utils/blockController"
import { isCtrlOrCmd, isTargetEditable } from "@/utils/helpers"

const store = useStudioStore()
const canvasStore = useCanvasStore()

export function useStudioEvents() {
	useEventListener(document, "contextmenu", async (e) => {
		const target =
			<HTMLElement | null>(e.target as HTMLElement)?.closest("[data-component-layer-id]") ||
			(e.target as HTMLElement)?.closest("[data-component-id]")
		if (target) {
			const blockId = target.dataset.componentLayerId || target.dataset.componentId
			const block = canvasStore.activeCanvas?.findBlock(blockId as string)
			if (block) {
				canvasStore.activeCanvas?.selectBlock(block, e)

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
	});

	useEventListener(document, "keydown", (e) => {
		if (isTargetEditable(e)) return

		// delete
		if ((e.key === "Backspace" || e.key === "Delete") && blockController.isAnyBlockSelected()) {
			for (const block of blockController.getSelectedBlocks()) {
				canvasStore.activeCanvas?.removeBlock(block, e.shiftKey)
			}
			clearSelection()
			e.stopPropagation()
			return
		}

		// duplicate
		if (e.key === "d" && isCtrlOrCmd(e)) {
			if (blockController.isAnyBlockSelected() && !blockController.multipleBlocksSelected()) {
				e.preventDefault();
				const block = blockController.getSelectedBlocks()[0];
				block.duplicateBlock();
			}
			return;
		}

		// undo
		if (e.key === "z" && isCtrlOrCmd(e) && !e.shiftKey && canvasStore.activeCanvas?.history?.canUndo()) {
			canvasStore.activeCanvas?.history.undo()
			e.preventDefault()
			return;
		}

		// redo
		if (e.key === "z" && e.shiftKey && isCtrlOrCmd(e) && canvasStore.activeCanvas?.history?.canRedo) {
			canvasStore.activeCanvas?.history.redo();
			e.preventDefault();
			return;
		}
	})

}

const clearSelection = () => {
	blockController.clearSelection();
	if (document.activeElement instanceof HTMLElement) {
		document.activeElement.blur();
	}
};