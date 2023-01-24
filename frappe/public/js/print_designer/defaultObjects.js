import { useMainStore } from "./store/MainStore";
import { useElementStore } from "./store/ElementStore";

export const createRectangle = (cordinates, parent = null) => {
	const ElementStore = useElementStore();
	const MainStore = useMainStore();

	if (parent === null) parent = ElementStore.Elements;
	let id = frappe.utils.get_random(10);
	if (cordinates instanceof MouseEvent) {
		cordinates = {
			startX: cordinates.offsetX,
			startY: cordinates.offsetY,
			pageX: cordinates.x,
			pageY: cordinates.y,
		};
	}
	const newRectangle = {
		id: id,
		type: "rectangle",
		DOMRef: null,
		childrens: [],
		parent: parent,
		isDraggable: false,
		isResizable: false,
		isDropZone: false,
		startX: cordinates.startX,
		startY: cordinates.startY,
		pageX: cordinates.pageX,
		pageY: cordinates.pageY,
		width: 0,
		height: 0,
		style: {},
		classes: [],
	};

	parent !== ElementStore.Elements
		? parent.childrens.push(newRectangle)
		: ElementStore.Elements.push(newRectangle);
	MainStore.lastCreatedElement = newRectangle;
	return newRectangle;
};
export const createImage = (cordinates, parent = null) => {
	const ElementStore = useElementStore();
	const MainStore = useMainStore();

	if (parent === null) parent = ElementStore.Elements;
	let id = frappe.utils.get_random(10);
	if (cordinates instanceof MouseEvent) {
		cordinates = {
			startX: cordinates.offsetX,
			startY: cordinates.offsetY,
			pageX: cordinates.x,
			pageY: cordinates.y,
		};
	}
	const newImage = {
		id: id,
		type: "image",
		DOMRef: null,
		parent: parent,
		isDraggable: false,
		isResizable: false,
		isDropZone: false,
		is_dynamic: false,
		image: null,
		startX: cordinates.startX,
		startY: cordinates.startY,
		pageX: cordinates.pageX,
		pageY: cordinates.pageY,
		width: 0,
		height: 0,
		style: {},
		classes: [],
	};

	parent !== ElementStore.Elements
		? parent.childrens.push(newImage)
		: ElementStore.Elements.push(newImage);
	MainStore.lastCreatedElement = newImage;
	return newImage;
};
export const createTable = (cordinates, parent = null) => {
	const ElementStore = useElementStore();
	const MainStore = useMainStore();

	if (parent === null) parent = ElementStore.Elements;
	let id = frappe.utils.get_random(10);
	if (cordinates instanceof MouseEvent) {
		cordinates = {
			startX: cordinates.offsetX,
			startY: cordinates.offsetY,
			pageX: cordinates.x,
			pageY: cordinates.y,
		};
	}
	const newTable = {
		id: id,
		type: "table",
		DOMRef: null,
		parent: parent,
		isDraggable: false,
		isResizable: false,
		isDropZone: false,
		table: null,
		columns: [],
		startX: cordinates.startX,
		startY: cordinates.startY,
		pageX: cordinates.pageX,
		pageY: cordinates.pageY,
		width: 0,
		height: 0,
		style: {},
		classes: [],
	};

	parent !== ElementStore.Elements
		? parent.childrens.push(newTable)
		: ElementStore.Elements.push(newTable);
	MainStore.lastCreatedElement = newTable;
	return newTable;
};

export const createText = (cordinates, parent = null) => {
	const ElementStore = useElementStore();
	const MainStore = useMainStore();

	if (parent === null) parent = ElementStore.Elements;
	let id = frappe.utils.get_random(10);
	if (cordinates instanceof MouseEvent) {
		cordinates = {
			startX: cordinates.offsetX,
			startY: cordinates.offsetY,
			pageX: cordinates.x,
			pageY: cordinates.y,
		};
	}
	const newStaticText = {
		id: id,
		type: "text",
		DOMRef: null,
		parent: parent,
		content: "",
		contenteditable: true,
		is_dynamic: false,
		isFixedSize: false,
		isDraggable: false,
		isResizable: false,
		isDropZone: false,
		startX: cordinates.startX - 5,
		startY: cordinates.startY - 16,
		pageX: cordinates.pageX,
		pageY: cordinates.pageY,
		width: 0,
		height: 0,
		style: {},
		classes: [],
	};
	parent !== ElementStore.Elements
		? parent.childrens.push(newStaticText)
		: ElementStore.Elements.push(newStaticText);
	MainStore.lastCreatedElement = newStaticText;
	return newStaticText;
};
export const createDynamicText = (cordinates, parent = null) => {
	const ElementStore = useElementStore();
	const MainStore = useMainStore();

	if (parent === null) parent = ElementStore.Elements;
	let id = frappe.utils.get_random(10);
	if (cordinates instanceof MouseEvent) {
		cordinates = {
			startX: cordinates.offsetX,
			startY: cordinates.offsetY,
			pageX: cordinates.x,
			pageY: cordinates.y,
		};
	}
	const newDynamicText = {
		id: id,
		type: "text",
		DOMRef: null,
		parent: parent,
		content: "",
		contenteditable: false,
		is_dynamic: true,
		isFixedSize: false,
		dynamicContent: [],
		selectedDyanmicText: [],
		isDraggable: false,
		isResizable: false,
		isDropZone: false,
		startX: cordinates.startX - 5,
		startY: cordinates.startY - 16,
		pageX: cordinates.pageX,
		pageY: cordinates.pageY,
		width: 0,
		height: 0,
		style: {},
		classes: [],
	};
	parent !== ElementStore.Elements
		? parent.childrens.push(newDynamicText)
		: ElementStore.Elements.push(newDynamicText);
	MainStore.lastCreatedElement = newDynamicText;
	return newDynamicText;
};
