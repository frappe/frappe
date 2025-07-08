import { reactive, toRaw, h, Ref, toRefs } from "vue"
import Block from "./block"
import getBlockTemplate from "./blockTemplate"
import { createDocumentResource, createListResource, createResource, confirmDialog } from "frappe-ui"
import { toast } from "vue-sonner"

import type { ObjectLiteral, BlockOptions, StyleValue, ExpressionEvaluationContext, SelectOption, HashString, RGBString } from "@/types"
import type { DataResult, DocumentResource, DocumentResult, Filters, Resource } from "@/types/Studio/StudioResource"
import type { Variable } from "@/types/Studio/StudioPageVariable"

function getBlockString(block: BlockOptions | Block): string {
	return jsToJson(getBlockCopyWithoutParent(block))
}

function getBlockInstance(options: BlockOptions | string, retainId = true): Block {
	if (typeof options === "string") {
		options = jsonToJs(options) as BlockOptions
	}
	if (!retainId) {
		const deleteComponentId = (block: BlockOptions) => {
			delete block.componentId
			for (let child of block.children || []) {
				deleteComponentId(child)
			}

			// clear componentId of slot children
			for (let slot of Object.values(block.componentSlots || {})) {
				if (Array.isArray(slot.slotContent)) {
					for (let child of slot.slotContent) {
						deleteComponentId(child)
					}
				}
			}
		}

		const deleteSlotId = (block: BlockOptions) => {
			for (let slot of Object.values(block.componentSlots || {})) {
				delete slot.slotId
			}
		}

		deleteComponentId(options)
		deleteSlotId(options)
	}
	return reactive(new Block(options))
}

function getComponentBlock(componentName: string) {
	return getBlockInstance({ componentName: componentName })
}

function getRootBlock(): Block {
	return getBlockInstance(getBlockTemplate("body"))
}

function getBlockCopy(block: BlockOptions | Block, retainId = false): Block {
	// remove parent block reference as JSON doesn't accept circular references
	const b = copyObject(getBlockCopyWithoutParent(block))
	return getBlockInstance(b, retainId)
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

function getBlockCopyWithoutParent(block: BlockOptions | Block) {
	const rawBlock = toRaw(block)
	const blockCopy = deepCloneObject(rawBlock, ["parentBlock"]) as BlockOptions
	delete blockCopy.parentBlock
	delete blockCopy.repeaterDataItem

	blockCopy.children = blockCopy.children?.map((child) => getBlockCopyWithoutParent(child))

	// remove parentBlock reference for slot children
	for (const slot of Object.values(blockCopy.componentSlots || {})) {
		if (Array.isArray(slot.slotContent)) {
			slot.slotContent = slot.slotContent.map((child) => getBlockCopyWithoutParent(child))
		}
	}

	return blockCopy
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

function kebabToCamelCase(str: string) {
	// convert border-color to borderColor
	return str.replace(/-([a-z])/g, function (g) {
		return g[1].toUpperCase();
	});
}

function copyObject<T>(obj: T) {
	if (!obj) return {}
	return jsonToJs(jsToJson(obj))
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

function isObjectEmpty(obj: object | null | undefined) {
	if (!obj) return true
	return Object.keys(obj).length === 0
}

function isJSONString(str: string) {
	try {
		jsonToJs(str)
	} catch (e) {
		return false
	}
	return true
}

function jsToJson(obj: ObjectLiteral): string {
	const replacer = (_key: string, value: any) => {
		// Preserve functions by converting them to strings
		if (typeof value === "function") {
			return value.toString()
		}
		// Handle circular references
		if (typeof value === "object" && value !== null) {
			if (value instanceof Set) {
			return [...value]
			}
			if (value instanceof Map) {
			return Object.fromEntries(value.entries())
			}
		}
		return value
	}
	return JSON.stringify(obj, replacer, 2)
}

function jsonToJs(json: string): any {
	const registeredComponents = window.__APP_COMPONENTS__ || {}
	const reviver = (_key: string, value: any) => {
		// Convert functions back to functions
		if (typeof value === "string" && value.startsWith("function")) {
			// provide access to render function & frappeUI lib for editing props
			const newFunc = new Function("scope", `with(scope) { return ${value}; }`)
			return newFunc({"h": h, ...registeredComponents})
		}
		return value
	}
	return JSON.parse(json, reviver)
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
	const appResource = createDocumentResource({
		doctype: "Studio App",
		name: appName,
		auto: true,
	})
	await appResource.get.promise
	return appResource.doc
}

// page
async function fetchPage(pageName: string) {
	const pageResource = createDocumentResource({
		doctype: "Studio Page",
		name: pageName,
	})
	await pageResource?.get?.promise
	return pageResource?.doc
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

const isDynamicValue = (value: string) => {
	// Check if the prop value is a string and contains a dynamic expression
	if (typeof value !== "string") return false
	return value && value.includes("{{") && value.includes("}}")
}

function getDynamicValue(value: string, context: ExpressionEvaluationContext) {
	let result = ""
	let lastIndex = 0

	if (!isDynamicValue(value)) {
		return evaluateExpression(value, context)
	}

	// Find all dynamic expressions in the prop value
	const matches = value.matchAll(/\{\{(.*?)\}\}/g)

	// Evaluate each dynamic expression and add it to the result
	for (const match of matches) {
		const expression = match[1].trim()
		const dynamicValue = evaluateExpression(expression, context)

		if (typeof dynamicValue === "object") {
			// for proptype as object, return the evaluated object as is
			// TODO: handle this more explicitly by checking the actual prop type
			return dynamicValue || undefined
		}

		// Append the static part of the string
		result += value.slice(lastIndex, match.index)
		// Append the evaluated dynamic value
		result += dynamicValue !== undefined ? String(dynamicValue) : ''
		// update lastIndex to the end of the current match
		lastIndex = match.index + match[0].length
	}

	// Append the final static part of the string
	result += value.slice(lastIndex)
	return result || undefined
}

function getEvaluatedFilters(filters: Filters | null = null, context: ExpressionEvaluationContext) {
	if (typeof filters === "string") {
		filters = JSON.parse(filters)
	}

	if (!filters) return null
	const evaluatedFilters: Filters = {}

	for (const key in filters) {
		let value = Array.isArray(filters[key]) ? filters[key][1] : filters[key]

		if (isDynamicValue(value)) {
			evaluatedFilters[key] = getDynamicValue(value, context)
		} else {
			evaluatedFilters[key] = value
		}
	}

	return evaluatedFilters
}

function evaluateExpression(expression: string, context: ExpressionEvaluationContext) {
	try {
		// Replace dot notation with optional chaining
		const safeExpression = expression.replace(/(\w+)(?:\.(\w+))+/g, (match) => {
			return match.split('.').join('?.')
		})

		// Create a function that takes the context as an argument
		const func = new Function('context', `
			with (context || {}) {
				try {
					return ${safeExpression};
				} catch (e) {
					return undefined;
				}
			}
		`)

		return func(context)
	} catch (error) {
		console.error(`Error evaluating expression: ${expression}`, error)
		return undefined
	}
}

function executeUserScript(script: string, variables: Record<string, any>, resources: Record<string, any>, repeaterContext?: Record<string, any>) {
	try {
		// Pass variable refs as context so that users can access variables without 'variable.' prefix
		// eg: - {{ variable_name }} in templates or variable_name.value in scripts
		const variablesRefs = toRefs(variables)
		const context = { ...variablesRefs, ...resources, ...repeaterContext }

		const scriptToExecute = `
			with (context) {
			${script}
			}
		`;
		const scriptFunction = new Function("context", scriptToExecute);
		scriptFunction(context, resources);
	} catch (error) {
		console.error(`Error executing the script: ${script}`, error)
	}
}

function getTransforms(resource: Resource) {
	/**
	 * Create a function that includes the user's transform function
	 * Invoke the transform function with data/doc
	 */
	if (resource.transform_results) {
		if (resource.resource_type === "Document") {
			return {
				transform: (doc: DocumentResult) => {
					const transformFn = new Function(resource.transform + "\nreturn transform")()
					return transformFn.call(null, doc);
				}
			}
		} else {
			return {
				transform: (data: DataResult) => {
					const transformFn = new Function(resource.transform + "\nreturn transform")()
					return transformFn.call(null, data);
				}
			}
		}
	}
	return {}
}

function getWhitelistedMethods(resource: DocumentResource) {
	if (resource.whitelisted_methods) {
		let whitelisted_methods = resource.whitelisted_methods
		if (typeof resource.whitelisted_methods === "string") {
			whitelisted_methods = JSON.parse(resource.whitelisted_methods)
		}
		const methods: Record<string, string> = {}
		whitelisted_methods.forEach((method: string) => methods[method] = method)
		return { whitelistedMethods: methods }
	}
	return {}
}

async function getDocumentResource(resource: DocumentResource, context: ExpressionEvaluationContext) {
	let docname = resource.document_name
	if (resource.fetch_document_using_filters && resource.filters) {
		// fetch the docname based on filters
		const docList = createListResource({
			doctype: resource.document_type,
			fields: ["name"],
			filters: getEvaluatedFilters(resource.filters, context),
			auto: true
		})
		await docList.list?.promise
		docname = docList.data?.[0]?.name
	}

	return createDocumentResource({
		doctype: resource.document_type,
		name: docname,
		auto: true,
		...getTransforms(resource),
		...getWhitelistedMethods(resource),
	})
}

function getNewResource(resource: Resource, context?: ExpressionEvaluationContext) {
	let fields = []
	if ('fields' in resource && typeof resource.fields === "string") {
		fields = JSON.parse(resource.fields)
	}

	switch (resource.resource_type) {
		case "Document":
			return getDocumentResource(resource, context)
		case "Document List":
			return createListResource({
				doctype: resource.document_type,
				fields: fields.length ? fields : "*",
				filters: getEvaluatedFilters(resource.filters, context),
				pageLength: resource.limit,
				auto: true,
				...getTransforms(resource),
			})
		case "API Resource":
			return createResource({
				url: resource.url,
				method: resource.method,
				auto: true,
				...getTransforms(resource),
			})
	}
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
		confirmDialog({
			title: title,
			message: message,
			onConfirm: ({ hideDialog }: { hideDialog: Function }) => {
				resolve(true);
				hideDialog();
			},
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
	getBlockString,
	getBlockInstance,
	getComponentBlock,
	getRootBlock,
	getBlockCopy,
	getBlockCopyWithoutParent,
	getBlockInfo,
	getComponentRoot,
	numberToPx,
	pxToNumber,
	kebabToCamelCase,
	copyObject,
	areObjectsEqual,
	isObjectEmpty,
	isJSONString,
	jsToJson,
	jsonToJs,
	mapToObject,
	replaceMapKey,
	isTargetEditable,
	generateId,
	// slots
	isHTML,
	// app
	fetchApp,
	// page
	fetchPage,
	findPageWithRoute,
	// data
	getAutocompleteValues,
	isDynamicValue,
	getDynamicValue,
	evaluateExpression,
	executeUserScript,
	getNewResource,
	// variables
	getInitialVariableValue,
	// dialog
	confirm,
	// colors
	HexToHSV,
	HSVToHex,
	RGBToHex,
	getRGB,
	// general utils
	isCtrlOrCmd,
	copyToClipboard,
	setClipboardData,
	getErrorMessage,
	throttle,
}
