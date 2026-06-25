import { defineStore } from "pinia"
import {
	ref, computed, watch, watchEffect, reactive, toRef, toRefs, unref,
	isRef, isReactive, shallowRef, readonly, markRaw, nextTick, effectScope,
	type ComputedRef, type EffectScope, h,
} from "vue"
import { watchDebounced } from "@vueuse/core"
import { createDocumentResource, createListResource, createResource, call } from "frappe-ui"
import { studioPageResources } from "@/data/studioResources"
import { studioVariables } from "@/data/studioVariables"
import { loadPageScriptModule } from "@/data/studioPageScripts"
import * as globalUtils from "@/utils/globalUtils"
import { getInitialVariableValue, getValueFromObject, setValueInObject } from "@/utils/helpers"
import { isDynamicValue, normalizeDynamicValue } from "@/utils/code"
import { isFunctionExpression, toOptionalChaining, getTopLevelBindings } from "@/utils/parseCode"
import type { Filters, Resource, DocumentResource, DataResult } from "@/types/Studio/StudioResource"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { Variable } from "@/types/Studio/StudioPageVariable"
import type { ExpressionEvaluationContext } from "@/types"
import type { Router } from "vue-router"

export const vueReactivityApis = {
	ref, reactive, computed, watch, watchEffect, watchDebounced,
	toRef, toRefs, unref, isRef, isReactive,
	shallowRef, readonly, markRaw, nextTick,
}

const useCodeStore = defineStore("codeStore", () => {
	const resources = ref<Record<string, Resource>>({})
	const variables = ref<Record<string, any>>({})
	const routeObject = ref<ComputedRef>()
	const routerObject = ref<Router | Readonly<Router>>()

	// shallowRef (not ref): a deep ref would wrap this in reactive() and auto-unwrap the nested refs
	const pageScriptBindings = shallowRef<Record<string, any>>({})
	const pageScriptTemplateBindings = computed(() => {
		const unwrapped: Record<string, any> = {}
		for (const key in pageScriptBindings.value) {
			unwrapped[key] = unref(pageScriptBindings.value[key])
		}
		return unwrapped
	})
	const pageScriptError = ref<string | null>(null)
	let pageScriptScope: EffectScope | null = null

	function setRouteObject(route: ComputedRef) {
		routeObject.value = route
	}

	function setRouterObject(router: Router | Readonly<Router>) {
		routerObject.value = router
	}

	async function setPageResources(page: StudioPage, setResourceConfig: boolean = false) {
		studioPageResources.filters = { parent: page.name }
		await studioPageResources.reload()
		resources.value = {}

		const resourcePromises = studioPageResources.data.map(async (resource: Resource) => {
			const newResource = await getNewResource(resource, {
				...variables.value,
				route: unref(routeObject.value),
				router: routerObject.value,
			})
			return {
				resource_name: resource.resource_name,
				value: newResource,
				resource_id: resource.resource_id,
				resource_type: resource.resource_type,
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
		variables.value = {}

		studioVariables.data.map((variable: Variable) => {
			variables.value[variable.variable_name] = getInitialVariableValue(variable)
		})
	}

	function getValueFromVariable(variablePath: string, localContext?: ExpressionEvaluationContext) {
		const context = { ...variables.value, ...pageScriptTemplateBindings.value, ...localContext }
		return getValueFromObject(context, variablePath)
	}

	function setValueInVariable(variablePath: string, value: any, localContext?: ExpressionEvaluationContext) {
		const pathParts = variablePath.split(".")
		const rootKey = pathParts[0]
		if (localContext && localContext[rootKey] !== undefined) {
			setValueInObject(localContext, variablePath, value)
			return
		}

		const binding = pageScriptBindings.value[rootKey]
		if (isRef(binding)) {
			if (pathParts.length === 1) {
				binding.value = value
			} else {
				setValueInObject(binding.value as Record<string, any>, pathParts.slice(1).join("."), value)
			}
			return
		}
		setValueInObject(variables.value, variablePath, value)
	}

	function disposePageScriptScope() {
		pageScriptScope?.stop()
		pageScriptScope = null
	}

	async function setPageScript(page: StudioPage, isStandardPage: boolean = false) {
		disposePageScriptScope()
		pageScriptBindings.value = {}
		pageScriptError.value = null

		if (isStandardPage) {
			pageScriptBindings.value = await loadCodePageScript(page.name)
			return
		}

		// Non-exported app: interpret the page.script field (live, no imports).
		const source = page.script || ""
		if (!source.trim()) return
		const bindingNames = getTopLevelBindings(source)
		pageScriptBindings.value = compilePageScript(source, bindingNames)
	}

	async function loadCodePageScript(pageName: string): Promise<Record<string, any>> {
		const mod = await loadPageScriptModule(pageName)
		return runPageScriptSetup(mod?.default)
	}

	// Run a compiled page setup() in a fresh effect scope and return its top-level bindings. Shared
	// by initial load and HMR: on a hot update we already hold the new module, so we re-run its
	// setup directly instead of re-importing.
	async function runPageScriptSetup(setup: unknown): Promise<Record<string, any>> {
		disposePageScriptScope()
		if (typeof setup !== "function") return {}
		try {
			// setup(ctx) gets the live execution context (resources/variables/route/router) and may
			// be async (e.g. awaiting a resource fetch). Effects (watch/computed) created BEFORE the
			// first await are owned by the page scope; declare them before awaiting so they're
			// disposed on navigation.
			const bindings = runInPageScriptScope(() => (setup as Function)(scriptContext.value))
			return (await bindings) || {}
		} catch (error) {
			reportPageScriptError(error)
			return {}
		}
	}

	// HMR: the active page's script (or a composable/util it imports) was edited. Re-run its setup
	// with the freshly hot-loaded module so new refs/computed and changed dependency code take
	// effect on the canvas without a reload. (Pinia stores keep their singleton state — they refresh
	// their code only via their own acceptHMRUpdate.)
	async function applyPageScriptHMR(setup: unknown) {
		pageScriptError.value = null
		pageScriptBindings.value = await runPageScriptSetup(setup)
	}

	function reportPageScriptError(error: unknown) {
		console.error("Error running page script", error)
		pageScriptError.value = error instanceof Error ? error.message : String(error)
	}

	function runInPageScriptScope(run: () => any): any {
		// Reactive effects (watch/watchEffect/computed) created synchronously during `run` are
		// owned by this scope so they're disposed on the next navigation / recompile.
		pageScriptScope = effectScope(true)
		let result: any
		pageScriptScope.run(() => {
			try {
				result = run()
			} catch (error) {
				reportPageScriptError(error)
			}
		})
		return result
	}

	function compilePageScript(source: string, bindingNames: string[]) {
		// Run the page script source once, like a Vue `<script setup>`, and return every top-level
		// binding (refs/reactive/computed/functions/classes). Free identifiers resolve through a
		// proxy over the LIVE execution context, so the script sees the Vue reactivity APIs and
		// variables/resources/modules — including ones registered a tick later. The source is
		// always run (even with no named bindings) so watcher-only scripts still take effect.
		const liveContext = new Proxy(
			{},
			{
				has(_target, key) {
					// let globals (console, Function, …) fall through to the outer scope
					if (key === Symbol.unscopables) return false
					return key in interpretedScriptContext.value
				},
				get(_target, key) {
					return (interpretedScriptContext.value as Record<string | symbol, any>)[key]
				},
			},
		)
		return runInPageScriptScope(() => {
			const factory = new Function(
				"context",
				`with (context) {
					${source}
					return { ${bindingNames.join(", ")} };
				}`,
			)
			return factory(liveContext)
		}) || {}
	}

	const evalContext = computed(() => {
		return {
			...variables.value,
			...resources.value,
			...pageScriptTemplateBindings.value,
			...globalUtils,
			route: unref(routeObject.value),
			router: routerObject.value,
		}
	})

	// Base context for every script scope — event/success/error handlers, function-value props, and page-script setup.
	const scriptContext = computed(() => {
		const variablesRefs = toRefs(variables.value)
		return {
			...variablesRefs,
			...resources.value,
			...pageScriptBindings.value,
			...globalUtils,
			route: unref(routeObject.value),
			router: routerObject.value,
		}
	})

	// for non-standard pages: scriptContext + vueReactivityApis since it can't import them
	const interpretedScriptContext = computed(() => {
		return {
			...vueReactivityApis,
			...scriptContext.value,
		}
	})

	function getDynamicValue(value: string, localContext: ExpressionEvaluationContext) {
		let result = ""
		let lastIndex = 0

		const context = { ...evalContext.value, ...localContext }

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

			// If the whole value is a single dynamic expression, return the normalized evaluated value
			// e.g. value === "{{ showTooltip }}" should return boolean true/false if appropriate
			if (value.trim().match(/^\{\{.*\}\}$/)) {
				return normalizeDynamicValue(dynamicValue)
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

	function evaluateDynamicValues(value: string | object | number, localContext: ExpressionEvaluationContext = {}): any {
		/* recurse into arrays/objects and evaluate dynamic expressions */
		if (typeof value === "string") {
			if (isDynamicValue(value)) {
				return getDynamicValue(value, localContext)
			}
			if (isFunctionExpression(value)) {
				const func = stringToFunction(value, localContext)
				if (typeof func === "function") {
					return func
				}
			}
			return value
		}

		if (Array.isArray(value)) {
			return value.map((item) => evaluateDynamicValues(item, localContext))
		}

		if (value !== null && typeof value === "object") {
			const result: Record<string, any> = {}
			for (const [key, val] of Object.entries(value)) {
				result[key] = evaluateDynamicValues(val, localContext)
			}
			return result
		}

		return value
	}

	function evaluateExpression(expression: string, localContext: ExpressionEvaluationContext) {
		try {
			const context = { ...evalContext.value, ...localContext }
			// Replace dot notation with optional chaining via AST
			const safeExpression = toOptionalChaining(expression)

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
		eventArgs?: any[],
	) {
		try {
			const context = { ...scriptContext.value, ...repeaterContext, ...componentContext, eventArgs }

			const scriptToExecute = `
				with (context) {
				${script}
				if (typeof handleEvent === "function") {
					return handleEvent(...(context.eventArgs || []));
				}
				}
			`;
			const scriptFunction = new Function("context", scriptToExecute);
			return scriptFunction(context);
		} catch (error) {
			console.error(`Error executing the script: ${script}`, error)
		}
	}

	function handleSuccess(
		script: string,
		data: DataResult,
		repeaterContext?: Record<string, any>,
		componentContext?: Record<string, any>,
		eventArgs?: any[],
	) {
		try {
			const context = {
				...scriptContext.value,
				...repeaterContext,
				...componentContext,
				eventArgs,
				data,
			}

			const successFn = new Function(
				"ctx",
				`with(ctx) {
					${script}
					return onSuccess(data);
				}`,
			)
			return successFn(context)
		} catch (error) {
			console.error(`Error executing success script: ${script}`, error)
		}
	}

	function handleError(
		script: string,
		error: any,
		repeaterContext?: Record<string, any>,
		componentContext?: Record<string, any>,
		eventArgs?: any[],
	) {
		try {
			const context = {
				...scriptContext.value,
				...repeaterContext,
				...componentContext,
				eventArgs,
				error,
			}

			const errorFn = new Function(
				"ctx",
				`with(ctx) {
					${script}
					return onError(error);
				}`,
			)
			return errorFn(context)
		} catch (err) {
			console.error(`Error executing error script: ${script}`, err)
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
					auto: resource.auto,
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
					auto: resource.auto,
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
				"studio.api.get_docname",
				{ doctype: resource.document_type, filters: getEvaluatedFilters(resource.filters, context) }
			)
		}

		return createDocumentResource({
			doctype: resource.document_type,
			name: docname,
			auto: resource.auto,
			...getTransforms(resource),
			...getSuccessErrorHandlers(resource),
			...getWhitelistedMethods(resource),
		})
	}

	const getEvaluatedFilters = (filters: Filters | null = null, context: ExpressionEvaluationContext) => {
		if (!filters) return
		if (typeof filters === "string") {
			filters = JSON.parse(filters)
		}

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
		if (resource.transform) {
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
			handlers["onSuccess"] = (data: DataResult) => {
				return handleSuccess(resource.on_success!, data)
			}
		}
		if (resource.on_error) {
			handlers["onError"] = (error: any) => {
				return handleError(resource.on_error!, error)
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

	function stringToFunction(value: string, localContext: Record<string, any>): Function | string {
		/**
		 * Convert a function string to an actual function
		 * Used for component props that have function values
		 */
		const registeredComponents = window.__APP_COMPONENTS__ || {}

		try {
			const fn = new Function(
				"h",
				...Object.keys(registeredComponents),
				...Object.keys(scriptContext.value),
				...Object.keys(localContext),
				`return (${value})`
			)
			return fn(h, ...Object.values(registeredComponents), ...Object.values(scriptContext.value), ...Object.values(localContext))
		} catch (e) {
			return value
		}
	}

	return {
		setRouteObject,
		setRouterObject,
		routeObject,
		routerObject,
		// resources
		resources,
		setPageResources,
		// variables
		variables,
		setPageVariables,
		getValueFromVariable,
		setValueInVariable,
		// page script
		pageScriptBindings,
		pageScriptTemplateBindings,
		pageScriptError,
		setPageScript,
		applyPageScriptHMR,
		// code execution
		evalContext,
		scriptContext,
		interpretedScriptContext,
		getDynamicValue,
		evaluateDynamicValues,
		executeUserScript,
		handleSuccess,
		handleError,
		getAPIParams,
		stringToFunction,
	}
})

export default useCodeStore