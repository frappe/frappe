import { reactive, toRaw, h, Ref } from "vue"
import Block from "./block"
import getBlockTemplate from "./blockTemplate"
import * as frappeUI from "frappe-ui"

import { createDocumentResource, createListResource, createResource } from "frappe-ui"

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

function numberToPx(number: number, round: boolean = true): string {
	/* appends "px" to number with optional rounding */
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

function areObjectsEqual(obj1: any, obj2: any): boolean {
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

function isObjectEmpty(obj: any) {
	return Object.keys(obj).length === 0
}

function jsToJson(obj: any): string {
	const replacer = (key: string, value: any) => {
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
	const reviver = (key: string, value: any) => {
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

// page
async function fetchPage(pageName: string) {
	const pageResource = createDocumentResource({
		doctype: "Studio Page",
		name: pageName,
	})
	await pageResource.get.promise
	return pageResource.doc
}

async function findPageWithRoute(route: string) {
	let pageName = createResource({
		url: "studio.studio.doctype.studio_page.studio_page.find_page_with_route",
		method: "GET",
		params: { route: `studio-app/${route}` },
	})
	await pageName.fetch()
	pageName = pageName.data
	return fetchPage(pageName)
}

// data
function getAutocompleteValues(data: any[]) {
	return (data || []).map((d) => d["value"])
}

const isDynamicValue = (value: any) => {
	if (typeof value !== "string") return false
	return value && value.startsWith("{{") && value.endsWith("}}")
}

function getDynamicValue(object: any, pathToProperty: string) {
	let obj = object
	for (const key of pathToProperty.split(".")) {
		obj = obj?.[key]
	}
	return obj || undefined
}

function getNewResource(resource) {
	const fields = JSON.parse(resource.fields || "[]")
	switch (resource.resource_type) {
		case "Document Resource":
			return createDocumentResource({
				doctype: resource.document_type,
				name: resource.document_name,
				auto: true,
			})
		case "List Resource":
			return createListResource({
				doctype: resource.document_type,
				fields: fields.length ? fields : "*",
				auto: true,
			})
		case "API Resource":
			return createResource({
				url: resource.url,
				method: resource.method,
				auto: true,
			})
	}
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
	// page
	fetchPage,
	findPageWithRoute,
	// data
	getAutocompleteValues,
	isDynamicValue,
	getDynamicValue,
	getNewResource,
}
