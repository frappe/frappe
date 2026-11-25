import { Ref, toRaw } from "vue"
import { createResource } from "frappe-ui"
import DOMPurify from "dompurify"

import type { StyleValue } from "@/runtime/types"
import type { Variable } from "@/runtime/types/Studio/StudioPageVariable"

function isEditor() {
	return window.location.pathname.startsWith("/studio/")
}

function deepCloneObject(obj: any, skipKeys: string[] | null = null): any {
	// Read the raw object, not the Vue reactive proxy. It is not necessary for Vue to track
	// a copy, and it is much slower to read through the proxy.
	obj = toRaw(obj)
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

function kebabToCamelCase(str: string) {
	// convert border-color to borderColor
	return str.replace(/-([a-z])/g, function (g) {
		return g[1].toUpperCase();
	});
}

function isObjectEmpty(obj: object | null | undefined | any): boolean {
	if (!obj) return true
	return Object.keys(obj).length === 0
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

function generateId() {
	return Math.random().toString(36).substr(2, 9);
}

// Fetches the page definition (blocks + resources + variables) in one unprivileged call.
// Data the page renders stays permission-checked by the endpoints its resources call.
async function fetchAppPage(appName: string, pageName: string, preview: boolean = false) {
	const page = createResource({
		url: "frappe.studio.doctype.studio_page.studio_page.get_page",
		method: "GET",
		params: { app_name: appName, page_name: pageName, preview },
		// a published page changes only on publish; the preview must see every draft save
		cache: preview ? undefined : ["studio-page", pageName],
	})
	// a cached definition mounts at once and refreshes in the background for the next visit
	if (page.fetched) {
		page.reload().catch(() => {})
		return page.data
	}
	try {
		await page.fetch()
	} catch (error) {
		return null
	}
	return page.data
}

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

function scrub(txt: string | null | undefined) {
	if (!txt) return ""
	return txt.replace(/ |-/g, "_").toLowerCase()
}

function sanitizeHTML(html?: string): string {
	return DOMPurify.sanitize(html ?? "", { ADD_TAGS: ["use"] })
}

export {
	isEditor,
	deepCloneObject,
	getComponentRoot,
	numberToPx,
	kebabToCamelCase,
	isObjectEmpty,
	setValueInObject,
	generateId,
	fetchAppPage,
	getInitialVariableValue,
	scrub,
	sanitizeHTML,
}
