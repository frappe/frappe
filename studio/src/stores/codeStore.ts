import { defineStore } from "pinia"
import { ref, computed, watch, type WatchStopHandle, ComputedRef, toRefs } from "vue"
import { createDocumentResource, createListResource, createResource, call } from "frappe-ui"
import { studioPageResources } from "@/data/studioResources"
import { studioVariables } from "@/data/studioVariables"
import { studioWatchers } from "@/data/studioWatchers"
import { getInitialVariableValue, getValueFromObject, setValueInObject } from "@/utils/helpers"
import { isDynamicValue } from "@/utils/code"
import type { Filters, Resource, DocumentResource } from "@/types/Studio/StudioResource"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { Variable } from "@/types/Studio/StudioPageVariable"
import type { StudioPageWatcher } from "@/types/Studio/StudioPageWatcher"
import type { ExpressionEvaluationContext } from "@/types"

const useCodeStore = defineStore("codeStore", () => {
	const resources = ref<Record<string, Resource>>({})
	const variables = ref<Record<string, any>>({})
	const activeWatchers = ref<Record<string, WatchStopHandle>>({})
	const routeObject = ref<ComputedRef>()

	function setRouteObject(route: ComputedRef) {
		routeObject.value = route?.value ?? route
	}

	async function setPageResources(page: StudioPage, setResourceConfig: boolean = false) {
		studioPageResources.filters = { parent: page.name }
		await studioPageResources.reload()

		const resourcePromises = studioPageResources.data.map(async (resource: Resource) => {
			const newResource = await getNewResource(resource, {
				...variables.value,
				route: routeObject.value,
			})
			return {
				resource_name: resource.resource_name,
				value: newResource,
			}
		})

		const resolvedResources = await Promise.all(resourcePromises)

		resolvedResources.forEach((item) => {
			resources.value[item.resource_name] = item.value
			if (setResourceConfig) {
				if (!item.value) return
				resources.value[item.resource_name].resource_id = item.resource_id
				resources.value[item.resource_name].resource_type = item.resource_type
			}
		})
	}

	async function setPageVariables(page: StudioPage) {
		studioVariables.filters = { parent: page.name }
		await studioVariables.reload()

		studioVariables.data.map((variable: Variable) => {
			variables.value[variable.variable_name] = getInitialVariableValue(variable)
		})
	}

	function getValueFromVariable(variablePath: string) {
		return getValueFromObject(variables.value, variablePath)
	}

	function setValueInVariable(variablePath: string, value: any) {
		setValueInObject(variables.value, variablePath, value)
	}

	async function setPageWatchers(page: StudioPage) {
		cleanupWatchers()
		studioWatchers.filters = { parent: page.name }
		await studioWatchers.reload()

		studioWatchers.data.map((watcher: StudioPageWatcher) => {
			setupWatcher(watcher)
		})
	}

	function setupWatcher(watcher: StudioPageWatcher) {
		const isDeep = typeof variables.value[watcher.source] === "object"
		const watcherFn = watch(
			() => variables.value[watcher.source],
			() => {
				executeUserScript(watcher.script, variables.value, resources.value)
			},
			{ deep: isDeep, immediate: watcher.immediate }
		)
		activeWatchers.value[watcher.name || watcher.source] = watcherFn
	}

	function cleanupWatchers() {
		Object.values(activeWatchers.value).forEach(stop => stop())
		activeWatchers.value = {}
	}

	const globalContext = computed(() => {
		return {
			...variables.value,
			...resources.value,
			route: routeObject.value,
		}
	})

	function getDynamicValue(value: string, localContext: ExpressionEvaluationContext) {
		let result = ""
		let lastIndex = 0

		const context = { ...globalContext.value, ...localContext }

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

	function evaluateExpression(expression: string, localContext: ExpressionEvaluationContext) {
		try {
			const context = { ...globalContext.value, ...localContext }
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
		repeaterContext?: Record<string, any>,
		componentContext?: Record<string, any>,
	) {
		try {
			// Pass variable refs as context so that users can access variables without 'variable.' prefix
			// eg: - {{ variable_name }} in templates or variable_name.value in scripts
			const variablesRefs = toRefs(variables.value)
			const context = { ...variablesRefs, ...resources.value, ...repeaterContext, ...componentContext }

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

	const getDocumentResource = async (resource: DocumentResource, context: ExpressionEvaluationContext) => {
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

	const getEvaluatedFilters = (filters: Filters | null = null, context: ExpressionEvaluationContext) => {
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

	const getTransforms = (resource: Resource) => {
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

	const getSuccessErrorHandlers = (resource: Resource) => {
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

	const getWhitelistedMethods = (resource: DocumentResource) => {
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

	return {
		setRouteObject,
		routeObject,
		// resources
		resources,
		setPageResources,
		// variables
		variables,
		setPageVariables,
		getValueFromVariable,
		setValueInVariable,
		// watchers
		setPageWatchers,
		// code execution
		getDynamicValue,
		executeUserScript,
		getAPIParams,
	}
})

export default useCodeStore