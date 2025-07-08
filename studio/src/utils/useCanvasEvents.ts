import type Block from "@/utils/block";
import useStudioStore from "@/stores/studioStore";
import getBlockTemplate from "@/utils/blockTemplate";
import {
	numberToPx,
	pxToNumber,
} from "@/utils/helpers";
import { clamp, useEventListener } from "@vueuse/core";
import { Ref } from "vue";
import type { CanvasProps, CanvasHistory } from "@/types/StudioCanvas"

const store = useStudioStore();

export function useCanvasEvents(
	container: Ref<HTMLElement>,
	canvasProps: CanvasProps,
	canvasHistory: CanvasHistory,
	getRootBlock: () => Block,
	findBlock: (componentId: string) => Block | null,
) {
	useEventListener(container, "mousedown", (ev: MouseEvent) => {
		const initialX = ev.clientX;
		const initialY = ev.clientY;
		if (store.mode === "select") {
			return;
		} else {
			const pauseId = canvasHistory.value?.pause();
			ev.stopPropagation();
			let element = document.elementFromPoint(ev.x, ev.y) as HTMLElement;
			let block = getRootBlock();
			if (element) {
				if (element.dataset.componentId) {
					block = findBlock(element.dataset.componentId) || block;
				}
			}
			let parentBlock = getRootBlock();
			if (element.dataset.componentId) {
				parentBlock = findBlock(element.dataset.componentId) || parentBlock;
				while (parentBlock && !parentBlock.canHaveChildren()) {
					parentBlock = parentBlock.getParentBlock() || getRootBlock();
				}
			}
			const child = getBlockTemplate(store.mode);
			const parentElement = document.body.querySelector(
				`.canvas [data-component-id="${parentBlock.componentId}"]`,
			) as HTMLElement;
			const parentOldPosition = parentBlock.getStyle("position");
			if (parentOldPosition === "static" || parentOldPosition === "inherit" || !parentOldPosition) {
				parentBlock.setBaseStyle("position", "relative");
			}
			const parentElementBounds = parentElement.getBoundingClientRect();
			let x = (ev.x - parentElementBounds.left) / canvasProps.scale;
			let y = (ev.y - parentElementBounds.top) / canvasProps.scale;
			const parentWidth = pxToNumber(getComputedStyle(parentElement).width);
			const parentHeight = pxToNumber(getComputedStyle(parentElement).height);

			const childBlock = parentBlock.addChild(child);
			if (!childBlock) return

			childBlock.setBaseStyle("position", "absolute");
			childBlock.setBaseStyle("top", numberToPx(y));
			childBlock.setBaseStyle("left", numberToPx(x));

			const mouseMoveHandler = (mouseMoveEvent: MouseEvent) => {
				mouseMoveEvent.preventDefault();
				let width = (mouseMoveEvent.clientX - initialX) / canvasProps.scale;
				let height = (mouseMoveEvent.clientY - initialY) / canvasProps.scale;
				width = clamp(width, 0, parentWidth);
				height = clamp(height, 0, parentHeight);
				const setFullWidth = width === parentWidth;
				childBlock.setBaseStyle("width", setFullWidth ? "100%" : numberToPx(width));
				childBlock.setBaseStyle("height", numberToPx(height));
			};
			useEventListener(document, "mousemove", mouseMoveHandler);
			useEventListener(
				document,
				"mouseup",
				() => {
					document.removeEventListener("mousemove", mouseMoveHandler);
					parentBlock.setBaseStyle("position", parentOldPosition || "static");
					childBlock.setBaseStyle("position", "static");
					childBlock.setBaseStyle("top", "auto");
					childBlock.setBaseStyle("left", "auto");
					setTimeout(() => {
						store.mode = "select";
					}, 50);
					if (parentBlock.isGrid()) {
						childBlock.setStyle("width", "auto");
						childBlock.setStyle("height", "100%");
					} else {
						if (pxToNumber(childBlock.getStyle("width")) < 100) {
							childBlock.setBaseStyle("width", "100%");
						}
						if (pxToNumber(childBlock.getStyle("height")) < 100) {
							childBlock.setBaseStyle("height", "200px");
						}
					}
					pauseId && canvasHistory.value?.resume(pauseId, true);
				},
				{ once: true },
			);
		}
	});
}