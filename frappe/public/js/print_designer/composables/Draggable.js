import interact from "@interactjs/interact";
import "@interactjs/actions/drag";
import "@interactjs/auto-start";
import "@interactjs/modifiers";
import { useMainStore } from "../store/MainStore";
import { useElementStore } from "../store/ElementStore";
import { recursiveChildrens } from "../utils";

export function useDraggable({
	element,
	restrict = "parent",
	dragMoveListener,
	dragStartListener,
	dragStopListener,
}) {
	if (interact.isSet(element["DOMRef"]) && interact(element["DOMRef"]).draggable().enabled)
		return;
	const MainStore = useMainStore();
	const ElementStore = useElementStore();
	let elementPreviousZAxis;
	let top, left, bottom, right;
	if (typeof restrict != "string") {
		let rect = restrict.getBoundingClientRect();
		(top = rect.top), (left = rect.left), (bottom = rect.bottom), (right = rect.right);
	}
	const restrictToParent = interact.modifiers.restrictRect({
		restriction:
			typeof restrict == "string"
				? restrict
				: {
						top,
						left,
						bottom,
						right,
				  },
	});
	interact(element["DOMRef"])
		.draggable({
			ignoreFrom: ".resizer",
			autoScroll: true,
			modifiers: [
				restrictToParent,
				interact.modifiers.snap({
					targets: MainStore.snapPoints,
					relativePoints: [{ x: 0, y: 0 }],
				}),
			],
			listeners: {
				move: dragMoveListener,
			},
		})
		.on("dragstart", dragStartListener)
		.on("dragend", function (e) {
			element.style && (element.style.zIndex = elementPreviousZAxis);
			dragStopListener && dragStopListener(e);
			if (element.DOMRef.className == "modal-dialog modal-sm") {
				return;
			}
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
					splicedElement = currentParent.splice(e.target.piniaElementRef.index, 1)[0];
				} else {
					splicedElement = currentParent.childrens.splice(
						e.target.piniaElementRef.index,
						1
					)[0];
				}
				splicedElement = { ...splicedElement };
				splicedElement.id = frappe.utils.get_random(10);
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
	return;
}
