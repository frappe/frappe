import { Ref } from "vue"
import { createDocumentResource, createResource, dialog } from "frappe-ui"
import { toast } from "frappe-ui"

import type { ObjectLiteral, StyleValue, SelectOption, HashString, RGBString } from "@/types"
import type { Variable } from "@/types/Studio/StudioPageVariable"
import type { StudioApp } from "@/types/Studio/StudioApp"

function isEditor() {
	return window.location.pathname.startsWith("/studio/")
}

function deepCloneObject(obj: any, skipKeys: string[] | null = null): any {
	if (!obj || typeof obj !== "object") {
		return obj
	}
	if (obj instanceof Date) {
		return new Date(obj)
	}
	if (Array.isArray(obj)) {
		return obj.map(item => deepCloneObject(item, skipKeys))
	}

	const clonedObj: any = {}
	for (const key in obj) {
		if (skipKeys?.includes(key)) continue
		clonedObj[key] = deepCloneObject(obj[key], skipKeys)
	}

	return clonedObj
}

type BlockInfo = {
	blockId: string
	breakpoint: string
}
function getBlockInfo(e: MouseEvent) {
	const target = (e.target as HTMLElement)?.closest(".__studio_component__") as HTMLElement
	return (target?.dataset || {}) as BlockInfo
}

const isTextNode = (el: Element) => {
	return el.nodeType === Node.TEXT_NODE
}

const isCommentNode = (el: Element) => {
	return el.nodeType === Node.COMMENT_NODE
}

function getComponentRoot(componentRef: Ref) {
	if (!componentRef.value) return null
	if (componentRef.value instanceof HTMLElement || componentRef.value instanceof SVGElement) {
		return componentRef.value
	} else {
		if (isTextNode(componentRef.value.$el) || isCommentNode(componentRef.value.$el)) {
			// access exposed ref
			const rootRef = componentRef.value.rootRef
			if (typeof rootRef === "function") {
				// options API exposes ref as a function
				return rootRef().$el
			} else {
				return rootRef
			}
		}
		return componentRef.value?.$el
	}
}

// css
function numberToPx(number: StyleValue, round: boolean = true): string {
	/* appends "px" to number with optional rounding */
	if (number === null || number === undefined) return ""
	if (typeof number === "string") {
		number = parseFloat(number)
	}
	number = round ? Math.round(number) : number;
	return `${number}px`;
}

function pxToNumber(px: string | number | null | undefined): number {
	if (!px) return 0
	if (typeof px === "number") return px

	const number = Number(px.replace("px", ""))
	if (isNaN(number)) return 0
	return number
}

/**
 * Extracts the numeric value and unit from a CSS value string
 * @param value - CSS value string (e.g., "10px", "1.5em", "20")
 * @returns Object containing the number and unit parts
 */
function extractNumberAndUnit(value: string): { number: string; unit: string } {
	const match = value.match(/([0-9.]+)([a-z%]*)/) || ["", "0", ""];
	return { number: match[1], unit: match[2] };
}


/**
 * Adds a unit to a number if it doesn't already have one
 * @param numberStr - String containing a number with or without a unit
 * @param unit - Default unit to add if none exists
 * @returns String with unit attached
 */
function addUnitToNumber(numberStr: string, unit: string): string {
	const match = numberStr.match(/^([0-9.]+)([a-z%]*)$/);
	if (match) {
		const [, number, existingUnit] = match;
		return existingUnit ? numberStr : number + unit;
	}
	return numberStr;
}

/**
 * Normalizes CSS values by adding default units where missing
 * Handles both single values and spacing properties with multiple values
 * @param value - CSS value string
 * @param unitOptions - Array of possible units, first is used as default
 * @param styleProperty - CSS property name (used to detect spacing properties)
 * @returns Normalized value string with units added
 */
function normalizeValueWithUnits(value: string, unitOptions: string[], styleProperty: string): string {
	if (!unitOptions.length) return value;

	const defaultUnit = unitOptions[0];
	const isSpacingProperty = styleProperty === "margin" || styleProperty === "padding";

	if (isSpacingProperty) {
		const parts = value.trim().split(/\s+/);
		if (parts.length > 1) {
			return parts.map((part) => addUnitToNumber(part, defaultUnit)).join(" ");
		}
	}

	return addUnitToNumber(value, defaultUnit);
}

function kebabToCamelCase(str: string) {
	// convert border-color to borderColor
	return str.replace(/-([a-z])/g, function (g) {
		return g[1].toUpperCase();
	});
}

function areObjectsEqual(obj1: ObjectLiteral, obj2: ObjectLiteral): boolean {
	const keys1 = Object.keys(obj1)
	const keys2 = Object.keys(obj2)

	if (keys1.length !== keys2.length) return false

	for (const key of keys1) {
		if (!obj2.hasOwnProperty(key)) return false

		if (typeof obj1[key] === "object" && typeof obj2[key] === "object") {
			if (!areObjectsEqual(obj1[key], obj2[key])) return false
		} else {
			if (obj1[key] !== obj2[key]) return false
		}
	}

	return true
}

function isObjectEmpty(obj: object | null | undefined | any): boolean {
	if (!obj) return true
	return Object.keys(obj).length === 0
}

function getValueFromObject(obj: object | null | undefined, key: string) {
	if (isObjectEmpty(obj)) return undefined
	const data = Object.assign({}, obj)
	const value = key
		.split(".")
		.reduce(
			(d: Record<string, any> | null, key) => (d && typeof d === "object" ? d[key] : null),
			data as Record<string, any>,
		)
	return value
}

function setValueInObject(obj: Record<string, any>, key: string, value: any) {
	if (isObjectEmpty(obj)) return

	const propertyPath = key.split(".")
	if (propertyPath.length === 1) {
		// top level key
		obj[key] = value
	} else {
		const targetProperty = propertyPath.pop()!
		// navigate to the parent object
		for (const key of propertyPath) {
			if (!obj[key] || typeof obj[key] !== "object") {
				obj[key] = {}
			}
			obj = obj[key]
		}
		// set the value on the parent object
		obj[targetProperty] = value
	}
}

function isPrivateKey(key: string) {
	return key.startsWith("_") || key.startsWith("__")
}

function objToArray(obj?: ObjectLiteral) {
	if (!obj) return []
	return Object.keys(obj || {}).map((key) => {
		if (!key) return
		return {
			label: key,
			value: obj[key],
		}
	})
}

const mapToObject = (map: Map<any, any>) => Object.fromEntries(map.entries());

function replaceMapKey(map: Map<any, any>, oldKey: string, newKey: string) {
	const newMap = new Map();
	map.forEach((value, key) => {
		if (key === oldKey) {
			newMap.set(newKey, value);
		} else {
			newMap.set(key, value);
		}
	});
	return newMap;
}

function isTargetEditable(e: Event) {
	const target = e.target as HTMLElement;
	const isEditable = target.isContentEditable;
	const isInput = target.tagName === "INPUT" || target.tagName === "TEXTAREA";
	return isEditable || isInput;
}

function generateId() {
	return Math.random().toString(36).substr(2, 9);
}

// slots
function isHTML(content: any) {
	if (typeof content !== 'string') return false
	return /<[a-z][\s\S]*>/i.test(content)
}

// app
async function fetchApp(appName: string) {
	if (!appName) return null
	const appResource = createDocumentResource({
		doctype: "Studio App",
		name: appName,
	})
	await appResource.reload()
	return appResource.doc
}

function openInDesk(app: StudioApp) {
	window.open(`/app/studio-app/${app.name}`, "_blank")
}

// page
async function fetchPage(pageName: string) {
	if (!pageName) return null
	const pageResource = createDocumentResource({
		doctype: "Studio Page",
		name: pageName,
	})
	await pageResource.reload()
	return pageResource.doc
}

async function findPageWithRoute(appName: string, pageRoute: string) {
	let pageName = createResource({
		url: "studio.studio.doctype.studio_page.studio_page.find_page_with_route",
		method: "GET",
		params: { app_name: appName, page_route: pageRoute },
	})
	await pageName.fetch()
	pageName = pageName.data
	return fetchPage(pageName)
}

// data
function getAutocompleteValues(data: SelectOption[]) {
	if (!data.length || typeof data[0] === "string") return data
	return (data || []).map((d) => d["value"])
}

function getParamsObj(params: { key: string; value: string }[]) {
	const paramsObj: { [key: string]: string } = {}
	params.forEach((param) => {
		if (param.key) {
			paramsObj[param.key] = param.value
		}
	})
	return paramsObj
}

function getParamsArray(params?: string | { [key: string]: string }) {
	if (!params) return []
	if (typeof params == "string") {
		params = JSON.parse(params || "{}")
	}
	const paramsArray: { key: string; value: string; name: string }[] = []
	Object.entries(params!).forEach(([key, value]) => {
		paramsArray.push({ key, value, name: key })
	})
	return paramsArray
}

// variables
const getInitialVariableValue = (variable: Variable) => {
	// cast variable's initial value as per variable type
	let initialValue = variable.initial_value
	if (variable.variable_type === "Number") {
		initialValue = Number(initialValue)
	} else if (variable.variable_type === "Boolean") {
		initialValue = (initialValue === "true")
	} else if (variable.variable_type === "Object" && typeof initialValue === "string") {
		initialValue = JSON.parse(initialValue)
	} else if (variable.variable_type === "String" && typeof initialValue === "string") {
		initialValue = JSON.parse(initialValue)
	}
	return initialValue
}

// dialogs
async function confirm(message: string, title: string = "Confirm"): Promise<boolean> {
	return new Promise((resolve) => {
		dialog.confirm({
			title: title,
			message: message,
			onConfirm: () => resolve(true),
			onCancel: () => resolve(false),
		});
	});
}

// colors
function HexToHSV(color: HashString): { h: number; s: number; v: number } {
	const [r, g, b] = color
		.replace("#", "")
		.match(/.{1,2}/g)
		?.map((x) => parseInt(x, 16)) || [0, 0, 0];

	const max = Math.max(r, g, b);
	const min = Math.min(r, g, b);
	const v = max / 255;
	const d = max - min;
	const s = max === 0 ? 0 : d / max;
	const h =
		max === min
			? 0
			: max === r
			? (g - b) / d + (g < b ? 6 : 0)
			: max === g
			? (b - r) / d + 2
			: (r - g) / d + 4;
	return { h: h * 60, s, v };
}

function HSVToHex(h: number, s: number, v: number): HashString {
	s /= 100;
	v /= 100;
	h /= 360;

	let r = 0,
		g = 0,
		b = 0;

	let i = Math.floor(h * 6);
	let f = h * 6 - i;
	let p = v * (1 - s);
	let q = v * (1 - f * s);
	let t = v * (1 - (1 - f) * s);

	switch (i % 6) {
		case 0:
			(r = v), (g = t), (b = p);
			break;
		case 1:
			(r = q), (g = v), (b = p);
			break;
		case 2:
			(r = p), (g = v), (b = t);
			break;
		case 3:
			(r = p), (g = q), (b = v);
			break;
		case 4:
			(r = t), (g = p), (b = v);
			break;
		case 5:
			(r = v), (g = p), (b = q);
			break;
	}
	r = Math.round(r * 255);
	g = Math.round(g * 255);
	b = Math.round(b * 255);
	return `#${[r, g, b].map((x) => x.toString(16).padStart(2, "0")).join("")}`;
}

function RGBToHex(rgb: RGBString): HashString {
	const [r, g, b] = rgb
		.replace("rgb(", "")
		.replace(")", "")
		.split(",")
		.map((x) => parseInt(x));
	return `#${[r, g, b].map((x) => x.toString(16).padStart(2, "0")).join("")}`;
}

function getRGB(color: HashString | RGBString | string | null): HashString | null {
	if (!color) {
		return null;
	}
	if (color.startsWith("rgb")) {
		return RGBToHex(color as RGBString);
	} else if (!color.startsWith("#") && color.match(/\b[a-fA-F0-9]{3,6}\b/g)) {
		return `#${color}` as HashString;
	}
	return color as HashString;
}

function isColorToken(tokenString?: string | null) {
	return tokenString?.startsWith("var(--")
}

function getColorFromToken(tokenString: string) {
	if (!tokenString) return tokenString
	if (!isColorToken(tokenString)) return tokenString
	return tokenString
		.replace("var(--", "")
		.replace(")", "")
		.split(",")[0]
		.trim()
}

// general utils
function isCtrlOrCmd(e: KeyboardEvent | MouseEvent) {
	return e.ctrlKey || e.metaKey;
}

function copyToClipboard(text: string | object) {
	if (typeof text !== "string") {
		text = JSON.stringify(text)
	}

	if (navigator.clipboard) {
		navigator.clipboard.writeText(text)
		toast.success("Copied to clipboard")
	} else {
		const textArea = document.createElement("textarea")
		textArea.value = text
		textArea.style.position = "fixed"
		document.body.appendChild(textArea)
		textArea.select()
		try {
			document.execCommand("copy")
			toast.success("Copied to clipboard")
		} catch (error) {
			toast.error("Copy to clipboard not supported")
		} finally {
			textArea.remove()
		}
	}
}

function setClipboardData(text: string | object, e: ClipboardEvent, copyFormat = "text/plain") {
	if (typeof text !== "string") {
		text = JSON.stringify(text);
	}
	e.clipboardData?.setData(copyFormat, text);
}

function getErrorMessage(err: any) {
	const lastLine = err.exc
		?.split('\n')
		.filter(Boolean)
		.at(-1)
		?.trim()
		.split(': ')
		.slice(1)
		.join(': ')
	return lastLine || err.message || err.toString()
}

function throttle<T extends (...args: any[]) => void>(func: T, wait: number = 1000) {
	let timeout: ReturnType<typeof setTimeout> | null = null
	let lastArgs: Parameters<T> | null = null
	let pending = false

	const invoke = (...args: Parameters<T>) => {
		lastArgs = args
		if (timeout) {
			pending = true
			return
		}

		func(...lastArgs);
		timeout = setTimeout(() => {
			timeout = null
			if (pending && lastArgs) {
				pending = false
				invoke(...lastArgs)
			}
		}, wait)
	};

	return invoke
}

function scrub(txt: string | null | undefined) {
	if (!txt) return ""
	return txt.replace(/ |-/g, "_").toLowerCase()
}

export {
	isEditor,
	deepCloneObject,
	getBlockInfo,
	getComponentRoot,
	// css
	numberToPx,
	pxToNumber,
	extractNumberAndUnit,
	normalizeValueWithUnits,
	kebabToCamelCase,
	areObjectsEqual,
	isObjectEmpty,
	getValueFromObject,
	setValueInObject,
	isPrivateKey,
	// maps & objects
	objToArray,
	mapToObject,
	replaceMapKey,
	isTargetEditable,
	generateId,
	// slots
	isHTML,
	// app
	fetchApp,
	openInDesk,
	// page
	fetchPage,
	findPageWithRoute,
	// data
	getAutocompleteValues,
	getParamsObj,
	getParamsArray,
	// variables
	getInitialVariableValue,
	// dialog
	confirm,
	// colors
	HexToHSV,
	HSVToHex,
	RGBToHex,
	getRGB,
	isColorToken,
	getColorFromToken,
	// general utils
	isCtrlOrCmd,
	copyToClipboard,
	setClipboardData,
	getErrorMessage,
	throttle,
	scrub,
}
