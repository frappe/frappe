import { toRefs } from "vue"
import type { ExpressionEvaluationContext } from "@/types"
import type { Filters, Resource, DocumentResource } from "@/types/Studio/StudioResource"
import { createDocumentResource, createListResource, createResource } from "frappe-ui"
import { call } from "frappe-ui"

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

function executeUserScript(
	script: string,
	variables: Record<string, any>,
	resources: Record<string, any>,
	repeaterContext?: Record<string, any>,
	componentContext?: Record<string, any>,
) {
	try {
		// Pass variable refs as context so that users can access variables without 'variable.' prefix
		// eg: - {{ variable_name }} in templates or variable_name.value in scripts
		const variablesRefs = toRefs(variables)
		const context = { ...variablesRefs, ...resources, ...repeaterContext, ...componentContext }

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

function getEvaluatedFilters(filters: Filters | null = null, context: ExpressionEvaluationContext) {
	if (typeof filters === "string") {
		filters = JSON.parse(filters)
	}

	if (!filters) return
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

function getAPIParams(params: Record<string, any> | string | null = null, context: ExpressionEvaluationContext) {
	if (!params) return null
	if (typeof params === "string") {
		params = JSON.parse(params)
	}
	if (params && typeof params === "object") {
		Object.entries(params).forEach(([key, value]) => {
			if (isDynamicValue(value)) {
				params[key] = getDynamicValue(value, context)
			}
		})
	}
	return params
}

function getTransforms(resource: Resource) {
	/**
	 * Create a function that includes the user's transform function
	 * Invoke the transform function with data/doc
	 */
	if (resource.transform_results) {
		if (resource.resource_type === "Document") {
			return {
				transform: (doc: any) => {
					const transformFn = new Function(resource.transform + "\nreturn transform")()
					return transformFn.call(null, doc);
				}
			}
		} else {
			return {
				transform: (data: any) => {
					const transformFn = new Function(resource.transform + "\nreturn transform")()
					return transformFn.call(null, data);
				}
			}
		}
	}
	return {}
}

function getSuccessErrorHandlers(resource: Resource) {
	const handlers: Record<string, Function> = {}
	if (resource.on_success) {
		handlers["onSuccess"] = (data: any) => {
			const successFn = new Function(resource.on_success + "\nreturn onSuccess")()
			return successFn.call(null, data);
		}
	}
	if (resource.on_error) {
		handlers["onError"] = (error: any) => {
			const errorFn = new Function(resource.on_error + "\nreturn onError")()
			return errorFn.call(null, error);
		}
	}
	return handlers
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
		docname = await call(
			"studio.api.get_document",
			{doctype: resource.document_type, filters: getEvaluatedFilters(resource.filters, context) }
		)
	}

	return createDocumentResource({
		doctype: resource.document_type,
		name: docname,
		auto: true,
		...getTransforms(resource),
		...getSuccessErrorHandlers(resource),
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
			const params: any = {
				doctype: resource.document_type,
				fields: fields.length ? fields : "*",
				filters: getEvaluatedFilters(resource.filters, context),
				pageLength: resource.limit,
				auto: true,
				...getTransforms(resource),
				...getSuccessErrorHandlers(resource),
			}
			if (resource.sort_field) {
				params["orderBy"] = `${resource.sort_field} ${resource.sort_order}`
			}
			return createListResource(params)
		case "API Resource":
			return createResource({
				url: resource.url,
				method: resource.method,
				params: getAPIParams(resource.params, context),
				auto: true,
				...getTransforms(resource),
				...getSuccessErrorHandlers(resource),
			})
	}
}

export {
	isDynamicValue,
	getDynamicValue,
	evaluateExpression,
	executeUserScript,
	getNewResource,
	getAPIParams,
}
