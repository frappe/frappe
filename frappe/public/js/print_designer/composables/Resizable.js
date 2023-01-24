import interact from "@interactjs/interact";
import "@interactjs/actions/resize";
import "@interactjs/auto-start";
import "@interactjs/modifiers";
import { useMainStore } from "../store/MainStore";
import { useElementStore } from "../store/ElementStore";
import { recursiveChildrens } from "../utils";

export function useResizable({
	element,
	resizeMoveListener,
	resizeStartListener,
	resizeStopListener,
	restrict = "parent",
}) {
	if (element && restrict) {
		if (interact.isSet(element.DOMRef) && interact(element.DOMRef).resizable().enabled) {
			return;
		}
		const MainStore = useMainStore();
		const ElementStore = useElementStore();
		interact(element.DOMRef)
			.resizable({
				ignoreFrom: ".resizer",
				edges: {
					left: ".resize-left",
					right: ".resize-right",
					bottom: ".resize-bottom",
					top: ".resize-top",
				},
				modifiers: [
					interact.modifiers.restrictEdges(),
					interact.modifiers.snapEdges({
						targets: MainStore.snapEdges,
					}),
				],
				listeners: {
					move: resizeMoveListener,
				},
			})
			.on("resizestart", resizeStartListener)
			.on("resizeend", function (e) {
				resizeStopListener && resizeStopListener(e);
				if (element.DOMRef.className == "modal-dialog modal-sm") {
					return;
				}
				if (element.parent == e.target.piniaElementRef.parent) return;
				if (
					!e.dropzone &&
					e.target.piniaElementRef.parent !== ElementStore.Elements &&
					!MainStore.lastCloned
				) {
					let splicedElement;
					let currentRect = e.target.getBoundingClientRect();
					let canvasRect = MainStore.mainContainer.getBoundingClientRect();
					let currentParent = e.target.piniaElementRef.parent;
					if (currentParent == ElementStore.Elements) {
						splicedElement = currentParent.splice(
							e.target.piniaElementRef.index,
							1
						)[0];
					} else {
						splicedElement = currentParent.childrens.splice(
							e.target.piniaElementRef.index,
							1
						)[0];
					}
					splicedElement = { ...splicedElement };
					splicedElement.startX = currentRect.left - canvasRect.left;
					splicedElement.startY = currentRect.top - canvasRect.top;
					splicedElement.parent = ElementStore.Elements;
					recursiveChildrens({ element: splicedElement, isClone: false });
					ElementStore.Elements.push(splicedElement);
					let droppedElement = new Object();
					droppedElement[splicedElement.id] = splicedElement;
					MainStore.isDropped = droppedElement;
				}
			});
	}

	return;
}
