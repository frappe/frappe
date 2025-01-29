import { CanvasProps } from "@/types"
import Block from "@/utils/block"
import { nextTick, reactive, ref, Ref } from "vue"
import { useElementBounding } from "@vueuse/core"

export function useCanvasUtils(
	canvasProps: CanvasProps,
	canvasContainer: Ref<HTMLElement | null>,
	canvas: Ref<HTMLElement | null>,
	rootComponent: Ref<Block>,
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
	};

	function getRootBlock() {
		return rootComponent.value;
	}

	function setRootBlock(newBlock: Block, resetCanvas = false) {
		rootComponent.value = newBlock;
		if (resetCanvas) {
			nextTick(() => {
				setScaleAndTranslate();
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

	return {
		setScaleAndTranslate,
		getRootBlock,
		setRootBlock,
		findBlock,
	};
}
