import { createDocumentResource, dialog } from "frappe-ui"
import { toast } from "frappe-ui"

import { isObjectEmpty } from "@/runtime/utils/helpers"

export * from "@/runtime/utils/helpers"
import type { ObjectLiteral, SelectOption, HashString, RGBString } from "@/types"
import type { StudioApp } from "@/types/Studio/StudioApp"
import type { StudioPage } from "@/runtime/types/Studio/StudioPage"

type BlockInfo = {
	blockId: string
	breakpoint: string
}
function getBlockInfo(e: MouseEvent) {
	const target = (e.target as HTMLElement)?.closest(".__studio_component__") as HTMLElement
	return (target?.dataset || {}) as BlockInfo
}

// css
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

function camelToKebabCase(str: string) {
	// convert borderColor to border-color
	return str.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)
}

function toTitleCase(cssProperty: string) {
	// convert border-color to Border Color
	return cssProperty
		.split("-")
		.filter(Boolean)
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ")
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
	// the first element in the path: `e.target` of a shadow root is its host
	const target = (e.composedPath()[0] ?? e.target) as HTMLElement;
	const isEditable = target.isContentEditable;
	const isInput = target.tagName === "INPUT" || target.tagName === "TEXTAREA";
	return isEditable || isInput;
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

function openAppInDesk(app: StudioApp) {
	window.open(`/app/studio-app/${app.name}`, "_blank")
}

function openPageInDesk(page: StudioPage) {
	window.open(`/app/studio-page/${page.name}`, "_blank")
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

// extract dynamic route variables from a vue-router route, e.g. "/articles/:category" -> ["category"]
function getRouteVariables(route: string): string[] {
	const variables = [] as string[]
	route.split("/").forEach((part) => {
		if (part.startsWith(":") && part.length > 1) {
			variables.push(part.slice(1))
		}
	})
	return variables
}

// data
function getAutocompleteValues(data: SelectOption[]) {
	if (!data.length || typeof data[0] === "string") return data
	return (data || []).map((d) => d["value"])
}

type EditableParam = { key: string; value: string; name?: string; isJSONValue?: boolean }
function getParamsObj(params: EditableParam[]) {
	const paramsObj: Record<string, unknown> = {}
	params.forEach((param) => {
		if (param.key) {
			paramsObj[param.key] = getStoredParamValue(param)
		}
	})
	return paramsObj
}

function getStoredParamValue(param: EditableParam) {
	if (!param.isJSONValue) return param.value
	try {
		return JSON.parse(param.value)
	} catch {
		return param.value
	}
}

function getParamsArray(params?: string | Record<string, unknown>) {
	if (!params) return []
	if (typeof params == "string") {
		params = JSON.parse(params || "{}")
	}
	const paramsArray: EditableParam[] = []
	Object.entries(params!).forEach(([key, value]) => {
		const _value = typeof value === "string" ? value : JSON.stringify(value)
		paramsArray.push({ key, value: _value ?? "", name: key, isJSONValue: typeof value !== "string" })
	})
	return paramsArray
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

export {
	getBlockInfo,
	// css
	pxToNumber,
	extractNumberAndUnit,
	normalizeValueWithUnits,
	camelToKebabCase,
	toTitleCase,
	areObjectsEqual,
	getValueFromObject,
	isPrivateKey,
	// maps & objects
	objToArray,
	mapToObject,
	replaceMapKey,
	isTargetEditable,
	// slots
	isHTML,
	// app
	fetchApp,
	openAppInDesk,
	openPageInDesk,
	// page
	fetchPage,
	getRouteVariables,
	// data
	getAutocompleteValues,
	getParamsObj,
	getParamsArray,
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
}
