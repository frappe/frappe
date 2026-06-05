import type { CanvasProps } from "@/types/StudioCanvas"
import Block from "@/utils/block"

import { nextTick, reactive, Ref } from "vue"
import { useCanvasHistory, type PauseId } from "@/utils/useCanvasHistory"
import { useElementBounding } from "@vueuse/core"
import { toast } from "frappe-ui"
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

	function setRootBlock(newBlock: Block, resetCanvas = false, resetHistory = true) {
		rootComponent.value = newBlock
		if (canvasHistory.value && resetHistory) {
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

	async function scrollIntoView(
		blockToFocus: Block,
		canvasProps: CanvasProps,
		canvasContainer: Ref<HTMLElement>,
		canvas: Ref<HTMLElement>,
	) {
		// wait for editor to render
		await new Promise((resolve) => setTimeout(resolve, 100));
		if (!selectedBlockIds.value.has(blockToFocus.componentId)) {
			blockToFocus.selectBlock();
		}
		await nextTick();
		// single nextTick is not enough, adding this to ensure the DOM is updated after selection
		await nextTick();

		if (
			!canvasContainer.value ||
			!canvas.value ||
			blockToFocus.isRoot() ||
			!blockToFocus.isVisible() ||
			blockToFocus.getParentBlock()?.isSVG()
		) {
			return;
		}
		const container = canvasContainer.value as HTMLElement;
		const containerRect = container.getBoundingClientRect();
		await nextTick();
		const selectedBlock = canvasContainer.value.querySelector(
			`.editor[data-component-id="${blockToFocus.componentId}"][selected=true]`,
		) as HTMLElement;
		if (!selectedBlock) {
			return;
		}
		const blockRect = reactive(useElementBounding(selectedBlock));
		// check if block is in view
		if (
			blockRect.top >= containerRect.top &&
			blockRect.bottom <= containerRect.bottom &&
			blockRect.left >= containerRect.left &&
			blockRect.right <= containerRect.right
		) {
			return;
		}

		let padding = 80;
		let paddingBottom = 200;
		const blockWidth = blockRect.width + padding * 2;
		const containerBound = container.getBoundingClientRect();
		const blockHeight = blockRect.height + padding + paddingBottom;

		const scaleX = containerBound.width / blockWidth;
		const scaleY = containerBound.height / blockHeight;
		const newScale = Math.min(scaleX, scaleY);

		const scaleDiff = canvasProps.scale - canvasProps.scale * newScale;
		if (scaleDiff > 0.2) {
			return;
		}

		if (newScale < 1) {
			canvasProps.scale = canvasProps.scale * newScale;
			await new Promise((resolve) => setTimeout(resolve, 100));
			await nextTick();
			blockRect.update();
		}

		padding = padding * canvasProps.scale;
		paddingBottom = paddingBottom * canvasProps.scale;

		// slide in block from the closest edge of the container
		const diffTop = containerRect.top - blockRect.top + padding;
		const diffBottom = blockRect.bottom - containerRect.bottom + paddingBottom;
		const diffLeft = containerRect.left - blockRect.left + padding;
		const diffRight = blockRect.right - containerRect.right + padding;

		if (diffTop > 0) {
			canvasProps.translateY += diffTop / canvasProps.scale;
		} else if (diffBottom > 0) {
			canvasProps.translateY -= diffBottom / canvasProps.scale;
		}

		if (diffLeft > 0) {
			canvasProps.translateX += diffLeft / canvasProps.scale;
		} else if (diffRight > 0) {
			canvasProps.translateX -= diffRight / canvasProps.scale;
		}
	}

	async function scrollBlockIntoView(blockToFocus: Block) {
		return scrollIntoView(
			blockToFocus,
			canvasProps,
			canvasContainer as unknown as Ref<HTMLElement>,
			canvas as unknown as Ref<HTMLElement>,
		);
	}

	return {
		setScaleAndTranslate,
		setupHistory,
		getRootBlock,
		setRootBlock,
		findBlock,
		removeBlock,
		toggleMode,
		scrollBlockIntoView,
	};
}
