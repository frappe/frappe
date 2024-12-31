import useStudioStore from "@/stores/studioStore"
import { useEventListener } from "@vueuse/core"

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
				store.componentContextMenu?.showContextMenu(e, block)
			}
		}
	});
}