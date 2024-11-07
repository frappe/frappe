import { reactive, toRaw, h, Ref } from "vue"
import Block from "./block"
import getBlockTemplate from "./blockTemplate"
import * as frappeUI from "frappe-ui"

import { createDocumentResource, createListResource, createResource, confirmDialog } from "frappe-ui"

import { ObjectLiteral, BlockOptions, StyleValue, ExpressionEvaluationContext, SelectOption } from "@/types"
import { DataResult, DocumentResource, DocumentResult, Filters, Resource } from "@/types/studioResource"
import { StudioPage } from "@/types/Studio/StudioPage"

function getBlockInstance(options: BlockOptions, retainId = true): Block {
	if (typeof options === "string") {
		options = jsonToJs(options)
	}
	if (!retainId) {
		const deleteComponentId = (block: BlockOptions) => {
			delete block.componentId
			for (let child of block.children || []) {
				deleteComponentId(child)
			}
		}
		deleteComponentId(options)
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

function getBlockCopyWithoutParent(block: BlockOptions | Block): BlockOptions {
	const blockCopy = { ...toRaw(block) }
	blockCopy.children = blockCopy.children?.map((child) => getBlockCopyWithoutParent(child))
	delete blockCopy.parentBlock
	return blockCopy
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

function isObjectEmpty(obj: object | null) {
	if (!obj) return true
	return Object.keys(obj).length === 0
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
	const reviver = (_key: string, value: any) => {
		// Convert functions back to functions
		if (typeof value === "string" && value.startsWith("function")) {
			// provide access to render function & frappeUI lib for editing props
			const newFunc = new Function("scope", `with(scope) { return ${value}; }`)
			return newFunc({"h": h, "frappeUI": frappeUI})
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

async function findPageWithRoute(appRoute: string, pageRoute: string) {
	let route = `studio-app`
	if (appRoute) {
		route += `/${appRoute}/`
	}
	route += pageRoute

	let pageName = createResource({
		url: "studio.studio.doctype.studio_page.studio_page.find_page_with_route",
		method: "GET",
		params: { route: route },
	})
	await pageName.fetch()
	pageName = pageName.data
	return fetchPage(pageName)
}

async function fetchAppPages(appRoute: string): Promise<StudioPage[]> {
	let appRoutes = createResource({
		url: "studio.studio.doctype.studio_app.studio_app.get_app_pages",
		method: "GET",
		params: { app_route: appRoute },
	})
	await appRoutes.fetch()
	return appRoutes.data
}

// data
function getAutocompleteValues(data: SelectOption[]) {
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
	if (!docname && resource.filters) {
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


export {
	getBlockInstance,
	getComponentBlock,
	getRootBlock,
	getBlockCopy,
	getBlockCopyWithoutParent,
	getComponentRoot,
	numberToPx,
	pxToNumber,
	kebabToCamelCase,
	copyObject,
	areObjectsEqual,
	isObjectEmpty,
	jsToJson,
	jsonToJs,
	mapToObject,
	replaceMapKey,
	// app
	fetchApp,
	fetchAppPages,
	// page
	fetchPage,
	findPageWithRoute,
	// data
	getAutocompleteValues,
	isDynamicValue,
	getDynamicValue,
	getNewResource,
	// dialog
	confirm,
}
