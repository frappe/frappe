/**
 *
 * @param {String} inputText
 * @param {'px'|'mm'|'cm'|'in'} defaultUnit px is considered by default
 * @example
 * parseFloatAndUnit("110.5 mm") => {
 * value: 110.5,
 * unit: "mm"
 * };
 * @returns {{value: number, unit: 'px'|'mm'|'cm'|'in' }}
 */
export const parseFloatAndUnit = (inputText, defaultUnit = "px") => {
	if (typeof inputText == "number") {
		return {
			value: inputText,
			unit: defaultUnit,
		};
	}
	const number = parseFloat(inputText.match(/[+-]?([0-9]*[.])?[0-9]+/g));
	const validUnits = [/px/, /mm/, /cm/, /in/];
	const unit = [];
	validUnits.forEach(
		(rx) =>
			rx.test(inputText) &&
			unit.indexOf(rx.exec(inputText)[0]) == -1 &&
			unit.push(rx.exec(inputText)[0])
	);
	return {
		value: number,
		unit: unit.length == 1 ? unit[0] : defaultUnit,
	};
};

import interact from "@interactjs/interact";
import { useMainStore } from "./store/MainStore";
import { useElementStore } from "./store/ElementStore";
import { useDraggable } from "./composables/Draggable";
import { useResizable } from "./composables/Resizable";
import { useDropZone } from "./composables/DropZone";

export const changeDraggable = (element) => {
	if (
		!element.isDraggable &&
		interact.isSet(element.DOMRef) &&
		interact(element.DOMRef).draggable().enabled
	) {
		interact(element.DOMRef).draggable().enabled = false;
	} else if (
		element.isDraggable &&
		interact.isSet(element.DOMRef) &&
		!interact(element.DOMRef).draggable().enabled
	) {
		interact(element.DOMRef).draggable().enabled = true;
	} else if (element.isDraggable && !interact.isSet(element.DOMRef)) {
		useDraggable(element.id);
	}
};

export const lockAxis = (element, toggle) => {
	if (toggle) {
		interact(element.DOMRef).options.drag.lockAxis = "start";
		interact(element.DOMRef).options.resize.modifiers.push(
			interact.modifiers.aspectRatio({
				ratio: "preserve",
				modifiers: [interact.modifiers.restrictSize({ max: "parent" })],
			})
		);
	} else {
		interact(element.DOMRef).options.drag.lockAxis = "xy";
		interact(element.DOMRef).options.resize.modifiers = interact(
			element.DOMRef
		).options.resize.modifiers.filter((e) => e.name != "aspectRatio");
	}
};

export const changeDropZone = (element) => {
	if (
		!element.isDropZone &&
		interact.isSet(element.DOMRef) &&
		interact(element.DOMRef).dropzone().enabled
	) {
		interact(element.DOMRef).dropzone().enabled = false;
	} else if (
		element.isDropZone &&
		interact.isSet(element.DOMRef) &&
		!interact(element.DOMRef).dropzone().enabled
	) {
		interact(element.DOMRef).dropzone().enabled = true;
	} else if (element.isDropZone && !interact.isSet(element.DOMRef)) {
		useDropZone(element.id);
	}
};

export const changeResizable = (element) => {
	if (
		!element.isResizable &&
		interact.isSet(element.DOMRef) &&
		interact(element.DOMRef).resizable().enabled
	) {
		interact(element.DOMRef).resizable().enabled = false;
	} else if (
		element.isResizable &&
		interact.isSet(element.DOMRef) &&
		!interact(element.DOMRef).resizable().enabled
	) {
		interact(element.DOMRef).resizable().enabled = true;
	} else if (element.isResizable && !interact.isSet(element.DOMRef)) {
		useResizable(element.id);
	}
};

import { useChangeValueUnit } from "./composables/ChangeValueUnit";
export const postionalStyles = (startX, startY, width, height) => {
	const MainStore = useMainStore();
	const convertUnit = (input) => {
		let convertedUnit = useChangeValueUnit({
			inputString: input,
			defaultInputUnit: "px",
			convertionUnit: MainStore.page.UOM,
		});
		return `${convertedUnit.value.toFixed(3)}${convertedUnit.unit}`;
	};
	return {
		position: "absolute",
		top: convertUnit(startY),
		left: convertUnit(startX),
		width: convertUnit(width),
		height: convertUnit(height),
		padding: "1px",
	};
};

export const setCurrentElement = (event, element) => {
	const MainStore = useMainStore();
	if (!event.shiftKey && !MainStore.getCurrentElementsValues.includes(element)) {
		MainStore.currentElements = {};
	}
	if (MainStore.getCurrentElementsId.length < 2 && !MainStore.currentElements[element.id]) {
		MainStore.currentElements[element.id] = element;
	}
	if (event.shiftKey && !event.metaKey) {
		MainStore.currentElements[element.id] = element;
		return;
	} else if (event.metaKey && event.shiftKey) {
		delete MainStore.currentElements[element.id];
		return;
	}
};
const childrensCleanUp = (parentElement, element, isClone, isMainElement) => {
	const MainStore = useMainStore();
	const ElementStore = useElementStore();
	!isMainElement && (element = { ...element });
	!isClone && element && deleteSnapObjects(element);
	element.id = frappe.utils.get_random(10);
	element.index = null;
	element.DOMRef = null;
	!isMainElement && (element.parent = parentElement);
	element.style = { ...element.style };
	element.classes = [...element.classes];
	element.snapPoints = [];
	element.snapEdges = [];
	if (["text", "image"].indexOf(element.type) != -1 && element.is_dynamic) {
		if (element.type === "text") {
			element.dynamicContent = [
				...element.dynamicContent.map((el) => {
					return { ...el };
				}),
			];
			element.selectedDyanmicText = [];
			MainStore.dynamicData.push(...element.dynamicContent);
		} else {
			element.image = { ...element.image };
			MainStore.dynamicData.push(...element.image);
		}
	}
	if (isMainElement && isClone) {
		if (parentElement.parent === ElementStore.Elements) {
			parentElement.parent.push(element);
		} else {
			parentElement.parent.childrens.push(element);
		}
	} else if (!isMainElement) {
		if (parentElement === ElementStore.Elements) {
			parentElement.push(element);
		} else {
			parentElement.childrens.push(element);
		}
		recursiveChildrens({ element, isClone, isMainElement: false });
	}
};
export const recursiveChildrens = ({ element, isClone = false, isMainElement = true }) => {
	const parentElement = element;
	const childrensArray = parentElement.childrens;
	isMainElement && childrensCleanUp(parentElement, element, isClone, isMainElement);
	parentElement.childrens = [];
	if (parentElement.type == "rectangle" && childrensArray.length > 0) {
		childrensArray.forEach((element) => {
			childrensCleanUp(parentElement, element, isClone, false);
		});
	}
};

export const updateElementParameters = (e) => {
	const MainStore = useMainStore();
	let parameters = MainStore.currentDrawListener.parameters;
	let restrict = MainStore.currentDrawListener.restrict;
	if (restrict && !e.metaKey) {
		if (parameters.isReversedY) {
			if (restrict.top > parameters.startY) {
				MainStore.lastCreatedElement.startY = restrict.top;
				MainStore.lastCreatedElement.height = Math.abs(
					parameters.height - (restrict.top - parameters.startY)
				);
			} else {
				MainStore.lastCreatedElement.startY = parameters.startY;
				MainStore.lastCreatedElement.height = parameters.height;
			}
		} else {
			if (restrict.bottom && restrict.bottom - parameters.startY < parameters.height) {
				MainStore.lastCreatedElement.height = Math.abs(
					restrict.bottom - parameters.startY
				);
			} else {
				MainStore.lastCreatedElement.startY = parameters.startY;
				MainStore.lastCreatedElement.height = parameters.height;
			}
		}
		if (parameters.isReversedX) {
			if (restrict.left > parameters.startX) {
				MainStore.lastCreatedElement.startX = restrict.left;
				MainStore.lastCreatedElement.width = Math.abs(
					parameters.width - (restrict.left - parameters.startX)
				);
			} else {
				MainStore.lastCreatedElement.startX = parameters.startX;
				MainStore.lastCreatedElement.width = parameters.width;
			}
		} else {
			if (restrict.right && restrict.right - parameters.startX < parameters.width) {
				MainStore.lastCreatedElement.width = Math.abs(restrict.right - parameters.startX);
			} else {
				MainStore.lastCreatedElement.startX = parameters.startX;
				MainStore.lastCreatedElement.width = parameters.width;
			}
		}
	} else {
		MainStore.lastCreatedElement.startX = parameters.startX;
		MainStore.lastCreatedElement.startY = parameters.startY;
		MainStore.lastCreatedElement.height = parameters.height;
		MainStore.lastCreatedElement.width = parameters.width;
	}
};

export const deleteSnapObjects = (element, recursive = false) => {
	const MainStore = useMainStore();
	if (!element) {
		return;
	}
	element.snapPoints.forEach((point) => {
		MainStore.snapPoints.splice(MainStore.snapPoints.indexOf(point), 1);
	});
	element.snapEdges.forEach((point) => {
		MainStore.snapEdges.splice(MainStore.snapEdges.indexOf(point), 1);
	});
	if (recursive && element.type == "rectangle" && element.childrens.length > 0) {
		element.childrens.forEach((el) => {
			deleteSnapObjects(el, recursive);
		});
	}
};

export const deleteCurrentElement = () => {
	const MainStore = useMainStore();
	const ElementStore = useElementStore();
	if (MainStore.getCurrentElementsValues.length === 1) {
		let curobj = MainStore.getCurrentElementsValues[0];
		if (curobj.parent == ElementStore.Elements) {
			deleteSnapObjects(curobj.parent.splice(curobj.index, 1)[0], true);
		} else {
			deleteSnapObjects(curobj.parent.childrens.splice(curobj.index, 1)[0], true);
		}
	} else {
		MainStore.getCurrentElementsValues.forEach((element) => {
			if (element.parent == ElementStore.Elements) {
				deleteSnapObjects(
					element.parent.splice(element.parent.indexOf(element), 1)[0],
					true
				);
			} else {
				deleteSnapObjects(
					element.parent.childrens.splice(
						element.parent.childrens.indexOf(element),
						1
					)[0],
					true
				);
			}
		});
	}
	MainStore.lastCreatedElement = null;
	MainStore.currentElements = {};
};

export const cloneElement = () => {
	const MainStore = useMainStore();
	const ElementStore = useElementStore();
	const clonedElements = {};
	MainStore.getCurrentElementsValues.forEach((element) => {
		const clonedElement = { ...element };
		recursiveChildrens({ element: clonedElement, isClone: true });
		clonedElements[clonedElement.id] = clonedElement;
		clonedElements[clonedElement.id] = clonedElement;
	});
	MainStore.currentElements = clonedElements;
	MainStore.lastCloned = clonedElements;
};

export const getSnapPointsAndEdges = (element) => {
	const boundingRect = {};
	const observer = new IntersectionObserver((entries) => {
		for (const entry of entries) {
			boundingRect["x"] = entry.boundingClientRect.x;
			boundingRect["y"] = entry.boundingClientRect.y;
		}
		observer.disconnect();
	});
	observer.observe(element.DOMRef);
	const MainStore = useMainStore();
	const rowSnapPoint = () => {
		if (MainStore.getCurrentElementsId.indexOf(element.id) != -1) return;
		return {
			x: boundingRect.x + element.width,
			y: boundingRect.y,
			range: 10,
			direction: "row-append",
		};
	};
	MainStore.snapPoints.push(rowSnapPoint);
	const columnSnapPoint = () => {
		if (MainStore.getCurrentElementsId.indexOf(element.id) != -1) return;
		observer.observe(element.DOMRef);
		return {
			x: boundingRect.x,
			y: boundingRect.y + element.height,
			range: 10,
			direction: "column-append",
		};
	};
	MainStore.snapPoints.push(columnSnapPoint);
	const leftSnapEdge = () => {
		if (MainStore.getCurrentElementsId.indexOf(element.id) != -1) return;
		observer.observe(element.DOMRef);
		return {
			x: boundingRect.x,
			range: 10,
			direction: "row-append",
		};
	};
	const rightSnapEdge = () => {
		if (MainStore.getCurrentElementsId.indexOf(element.id) != -1) return;
		observer.observe(element.DOMRef);
		return {
			x: boundingRect.x + element.width,
			range: 10,
			direction: "row-append",
		};
	};
	MainStore.snapEdges.push(leftSnapEdge, rightSnapEdge);
	const topSnapEdge = () => {
		if (MainStore.getCurrentElementsId.indexOf(element.id) != -1) return;
		observer.observe(element.DOMRef);
		return {
			y: boundingRect.y,
			range: 10,
			direction: "column-append",
		};
	};
	const bottomSnapEdge = () => {
		if (MainStore.getCurrentElementsId.indexOf(element.id) != -1) return;
		observer.observe(element.DOMRef);
		return {
			y: boundingRect.y + element.height,
			range: 10,
			direction: "column-append",
		};
	};
	MainStore.snapEdges.push(topSnapEdge, bottomSnapEdge);
	return {
		rowSnapPoint,
		columnSnapPoint,
		leftSnapEdge,
		rightSnapEdge,
		topSnapEdge,
		bottomSnapEdge,
	};
};
