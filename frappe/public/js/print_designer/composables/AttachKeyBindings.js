import { onMounted } from "vue";
import { useMainStore } from "../store/MainStore";
import { useElementStore } from "../store/ElementStore";
import { deleteCurrentElement, cloneElement } from "../utils";

export function useAttachKeyBindings() {
	const MainStore = useMainStore();
	const ElementStore = useElementStore();
	onMounted(() => {
		function updateStartXY(axis, value) {
			MainStore.getCurrentElementsValues.forEach((element) => {
				let restrict;
				if (element.parent === ElementStore.Elements) {
					restrict = MainStore.mainContainer.getBoundingClientRect();
				} else {
					restrict = element.parent.DOMRef.getBoundingClientRect();
				}
				if (element[`start${axis}`] + value <= -1) {
					element[`start${axis}`] = -1;
				} else if (
					element[`start${axis}`] + element[axis == "X" ? "width" : "height"] + value >=
					restrict[axis == "X" ? "width" : "height"] - 1
				) {
					element[`start${axis}`] =
						restrict[axis == "X" ? "width" : "height"] -
						element[axis == "X" ? "width" : "height"] -
						1;
				} else {
					element[`start${axis}`] += value;
				}
			});
		}
		function updateWidthHeight(key, value) {
			MainStore.getCurrentElementsValues.forEach((element) => {
				let restrict;
				if (element.parent === ElementStore.Elements) {
					restrict = MainStore.mainContainer.getBoundingClientRect();
				} else {
					restrict = element.parent.DOMRef.getBoundingClientRect();
				}
				if (element[key] + value <= -1) {
					element[key] = -1;
				} else if (
					element[key] + element[key == "width" ? "startX" : "startY"] + value >=
					restrict[key] - 1
				) {
					element[key] =
						restrict[key] - element[key == "width" ? "startX" : "startY"] - 1;
				} else {
					element[key] += value;
				}
			});
		}
		window.addEventListener(
			"keydown",
			function (e) {
				MainStore.isAltKey = e.altKey;
				MainStore.isShiftKey = e.shiftKey;
				if (
					!MainStore.openModal &&
					!MainStore.openDyanmicModal &&
					(!MainStore.isDrawing ||
						(MainStore.isDrawing &&
							!MainStore.currentDrawListener.parameters.isMouseDown)) &&
					MainStore.getCurrentElementsId.length &&
					["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].indexOf(e.code) >
						-1
				) {
					e.preventDefault();
					switch (e.code) {
						case "ArrowUp":
							if (e.altKey) {
								updateWidthHeight("height", e.shiftKey ? -10 : -1);
								break;
							}
							updateStartXY("Y", e.shiftKey ? -10 : -1);
							break;
						case "ArrowDown":
							if (e.altKey) {
								updateWidthHeight("height", e.shiftKey ? 10 : 1);
								break;
							}
							updateStartXY("Y", e.shiftKey ? 10 : 1);
							break;
						case "ArrowLeft":
							if (e.altKey) {
								updateWidthHeight("width", e.shiftKey ? -10 : -1);
								break;
							}
							updateStartXY("X", e.shiftKey ? -10 : -1);
							break;
						case "ArrowRight":
							if (e.altKey) {
								updateWidthHeight("width", e.shiftKey ? 10 : 1);
								break;
							}
							updateStartXY("X", e.shiftKey ? 10 : 1);
							break;
					}
				}
			},
			false
		);
		window.addEventListener("keyup", (e) => {
			if (MainStore.openDyanmicModal || MainStore.openModal) return;
			MainStore.isAltKey = e.altKey;
			MainStore.isShiftKey = e.shiftKey;
			if (e.ctrlKey && e.code == "KeyA") {
				let currentElements = {};
				ElementStore.Elements.forEach((element) => {
					currentElements[element.id] = element;
				});
				MainStore.currentElements = currentElements;
			} else if ((e.key == "T") | (e.key == "t")) {
				MainStore.setActiveControl("Text");
			} else if ((e.key == "C") | (e.key == "c")) {
				MainStore.setActiveControl("Components");
			} else if ((e.key == "M") | (e.key == "m")) {
				MainStore.setActiveControl("MousePointer");
			} else if ((e.key == "R") | (e.key == "r")) {
				MainStore.setActiveControl("Rectangle");
			} else if ((e.key == "H") | (e.key == "h")) {
				MainStore.setActiveControl("HTML");
			} else if ((e.key == "I") | (e.key == "i")) {
				MainStore.setActiveControl("Image");
			} else if ((e.key == "B") | (e.key == "b")) {
				MainStore.setActiveControl("Barcode");
			} else if ((e.key == "A") | (e.key == "a")) {
				MainStore.setActiveControl("Table");
			} else if (e.key === "Delete" || e.key === "Backspace") {
				deleteCurrentElement();
			} else if (e.ctrlKey && e.code == "KeyL") {
				MainStore.isLayerPanelEnabled = !MainStore.isLayerPanelEnabled;
			}
		});
	});
}
