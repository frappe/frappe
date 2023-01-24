import { useMainStore } from "../store/MainStore";
import { useElementStore } from "../store/ElementStore";
import { useDraw } from "./Draw";
import { addEventListener, removeEventListener } from "./EventListener";
import { useChangeValueUnit } from "./ChangeValueUnit";
export function useMarqueeSelection() {
	let canvas;
	let marqueeElement = document.createElement("div");
	let isElementInCanvas;
	let beforeDraw, callback;
	const MainStore = useMainStore();
	const ElementStore = useElementStore();

	const vMarquee = {
		mounted: (el, binding) => {
			if (binding.value) {
				beforeDraw = binding.value.beforeDraw;
				callback = binding.value.callback;
			} else {
				callback = undefined;
				beforeDraw = true;
			}
			canvas = el;
			addEventListener(canvas, "mousedown", mouseDown);
			addEventListener(canvas, "mouseup", mouseUp);
			addEventListener(canvas, "mouseleave", mouseUp);
			callback && callback(el);
		},
	};

	const { drawEventHandler, parameters } = useDraw();

	function mouseDown(e) {
		if (e.buttons != 1) return;
		if (e.target.id == "canvas" && MainStore.activeControl != "mouse-pointer") {
			MainStore.setActiveControl("MousePointer");
			MainStore.isMarqueeActive = true;
		}
		if (!MainStore[beforeDraw]) return;
		drawEventHandler.mousedown(e);
		addEventListener(canvas, "mousemove", mouseMove);
		if (!e.shiftKey && MainStore.getCurrentElementsId.length) {
			MainStore.currentElements = {};
		}
		if (!canvas) return;
		if (marqueeElement) {
			marqueeElement.remove();
		}
		marqueeElement = document.createElement("div");
		marqueeElement.className = "selection";
		marqueeElement.style.zIndex = 9999;
		marqueeElement.style.left = parameters.startX - canvas.getBoundingClientRect().left + "px";
		marqueeElement.style.top = parameters.startY - canvas.getBoundingClientRect().top + "px";
	}

	function mouseMove(e) {
		if (!MainStore[beforeDraw]) return;
		drawEventHandler.mousemove(e);
		if (
			!isElementInCanvas &&
			parameters.isMouseDown &&
			(parameters.width > 5 || parameters.height > 5)
		) {
			canvas.appendChild(marqueeElement);
			isElementInCanvas = true;
		}
		if (marqueeElement) {
			marqueeElement.style.width = Math.abs(parameters.width) + "px";
			marqueeElement.style.height = Math.abs(parameters.height) + "px";
			marqueeElement.style.left =
				parameters.startX -
				canvas.getBoundingClientRect().left -
				parameters.scrollX +
				"px";
			marqueeElement.style.top =
				parameters.startY - canvas.getBoundingClientRect().top - parameters.scrollY + "px";
		}
	}

	function mouseUp(e) {
		removeEventListener(canvas, "mousemove", mouseMove);
		if (!MainStore[beforeDraw]) return;
		drawEventHandler.mouseup(e);

		if (marqueeElement) {
			const inBounds = [];
			if (!e.shiftKey && MainStore.getCurrentElementsId.length) {
				MainStore.currentElements = {};
			}

			const a = {
				x: parameters.startX - canvas.getBoundingClientRect().left,
				y: parameters.startY - canvas.getBoundingClientRect().top,
				width: Math.abs(parameters.width),
				height: Math.abs(parameters.height) + canvas.scrollTop,
			};
			const mainContainerRect = MainStore.mainContainer.getBoundingClientRect();
			const marginTopInPX = useChangeValueUnit({
				inputString: MainStore.page.marginTop,
				defaultInputUnit: MainStore.page.UOM,
			}).value;
			a.x -=
				mainContainerRect.x - MainStore.toolbarWidth > 0
					? mainContainerRect.x - MainStore.toolbarWidth
					: 0;
			a.y -=
				mainContainerRect.y - marginTopInPX <= 110
					? marginTopInPX + 50
					: mainContainerRect.y - marginTopInPX - 110;
			for (const value of ElementStore.Elements) {
				const { id, startX, startY, width, height, DOMRef } = value;
				const b = {
					id,
					x: startX,
					y: startY,
					width,
					height,
					DOMRef,
				};

				if (isInBounds(a, b)) {
					inBounds.push(DOMRef);
					if (e.metaKey && e.shiftKey) {
						delete MainStore.currentElements[id];
					} else {
						MainStore.currentElements[id] = value;
					}
				}
			}
			marqueeElement.remove();
			marqueeElement = null;
			isElementInCanvas = false;
		}
	}
	function isInBounds(a, b) {
		return (
			a.x < b.x + b.width &&
			a.x + a.width > b.x &&
			a.y < b.y + b.height &&
			a.y + a.height > b.y
		);
	}
	return { mouseDown, mouseMove, mouseUp, canvas, vMarquee };
}
