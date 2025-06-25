import type { CanvasProps } from "@/types/StudioCanvas"
import Block from "@/utils/block"

import { nextTick, reactive, Ref } from "vue"
import { useCanvasHistory } from "@/utils/useCanvasHistory"
import { useElementBounding } from "@vueuse/core"
import { toast } from "vue-sonner"
import useCanvasStore from "@/stores/canvasStore"
import type { StudioMode } from "@/types"

const canvasStore = useCanvasStore()

export function useCanvasUtils(
	canvasProps: CanvasProps,
	canvasContainer: Ref<HTMLElement | null>,
	canvas: Ref<HTMLElement | null>,
	rootComponent: Ref<Block>,
	selectedBlockIds: Ref<Set<string>>,
	canvasHistory: Ref<null | any>,
) {
	// canvas positioning
	const containerBound = reactive(useElementBounding(canvasContainer));
	const canvasBound = reactive(useElementBounding(canvas));
	const setScaleAndTranslate = async () => {
		if (document.readyState !== "complete") {
			await new Promise((resolve) => {
				window.addEventListener("load", resolve);
			});
		}
		const paddingX = 300;
		const paddingY = 200;

		await nextTick();
		canvasBound.update();
		const containerWidth = containerBound.width;
		const canvasWidth = canvasBound.width / canvasProps.scale;

		canvasProps.scale = containerWidth / (canvasWidth + paddingX * 2);

		canvasProps.translateX = 0;
		canvasProps.translateY = 0;
		await nextTick();
		const scale = canvasProps.scale;
		canvasBound.update();
		const diffY = containerBound.top - canvasBound.top + paddingY * scale;
		if (diffY !== 0) {
			canvasProps.translateY = diffY / scale;
		}
		canvasProps.settingCanvas = false;
	}

	function setupHistory() {
		canvasHistory.value = useCanvasHistory(rootComponent, selectedBlockIds);
	}

	function getRootBlock() {
		return rootComponent.value;
	}

	function setRootBlock(newBlock: Block, resetCanvas = false) {
		rootComponent.value = newBlock
		if (canvasHistory.value) {
			canvasHistory.value.dispose();
			setupHistory();
		}
		if (resetCanvas) {
			nextTick(() => {
				setScaleAndTranslate()
			});
		}
	}

	const findBlock = (componentId: string, blocks?: Block[]): Block | null => {
		if (!blocks) {
			blocks = [getRootBlock()]
		}

		for (const block of blocks) {
			if (block.componentId === componentId) return block

			if (block.children) {
				const found = findBlock(componentId, block.children)
				if (found) return found
			}

			if (block.componentSlots) {
				for (const slot of Object.values(block.componentSlots)) {
					if (Array.isArray(slot.slotContent)) {
						const found = findBlock(componentId, slot.slotContent)
						if (found) return found
					}
				}
			}
		}
		return null
	}

	function removeBlock(block: Block, force: boolean = false) {
		if (block.componentId === "root") {
			toast.warning("Warning", {
				description: "Cannot delete root component",
			})
			return
		}
		const parentBlock = block.parentBlock
		if (!parentBlock) return
		const nextSibling = block.getSiblingBlock("next")
		if (canvasStore.activeCanvas?.activeBreakpoint === "desktop" || force) {
			parentBlock.removeChild(block)
		} else {
			block.toggleVisibility(false)
		}
		nextTick(() => {
			if (parentBlock.children.length) {
				if (nextSibling) {
					nextSibling.selectBlock()
				}
			}
		})
	}

	function toggleMode(mode: StudioMode) {
		if (!canvasContainer.value) return;
		const container = canvasContainer.value as HTMLElement;
		if (mode === "container") {
			container.style.cursor = "crosshair"
		} else {
			container.style.cursor = "default"
		}
	}

	return {
		setScaleAndTranslate,
		setupHistory,
		getRootBlock,
		setRootBlock,
		findBlock,
		removeBlock,
		toggleMode,
	};
}
