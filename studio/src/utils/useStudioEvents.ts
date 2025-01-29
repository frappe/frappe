import useStudioStore from "@/stores/studioStore"
import { useEventListener } from "@vueuse/core"
import blockController from "@/utils/blockController"

const store = useStudioStore()

export function useStudioEvents() {
	useEventListener(document, "contextmenu", async (e) => {
		const target =
			<HTMLElement | null>(e.target as HTMLElement)?.closest("[data-component-layer-id]") ||
			(e.target as HTMLElement)?.closest("[data-component-id]")
		if (target) {
			const blockId = target.dataset.componentLayerId || target.dataset.componentId
			const block = store.canvas?.findBlock(blockId as string)
			if (block) {
				store.selectBlock(block, e)

				const slotName = target.dataset.slotName
				if (slotName) {
					const slot = block.getSlot(slotName)
					if (slot) {
						store.selectSlot(slot)
					}
				}

				store.componentContextMenu?.showContextMenu(e, block)
			}
		}
	});

	useEventListener(document, "keydown", (e) => {
		if ((e.key === "Backspace" || e.key === "Delete") && blockController.isAnyBlockSelected()) {
			for (const block of blockController.getSelectedBlocks()) {
				store.canvas?.removeBlock(block, e.shiftKey)
			}
			clearSelection()
			e.stopPropagation()
			return
		}
	})
}

const clearSelection = () => {
	blockController.clearSelection();
	if (document.activeElement instanceof HTMLElement) {
		document.activeElement.blur();
	}
};