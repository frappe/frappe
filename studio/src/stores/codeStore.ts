import { defineStore } from "pinia"
import {
	ref, computed, watch, watchEffect, reactive, toRef, toRefs, unref,
	isRef, isReactive, shallowRef, readonly, markRaw, nextTick, effectScope,
	type ComputedRef, type EffectScope, type WatchStopHandle, h,
} from "vue"
import { watchDebounced } from "@vueuse/core"
import { createDocumentResource, createListResource, createResource, call } from "frappe-ui"
import { studioPageResources } from "@/data/studioResources"
import { studioVariables } from "@/data/studioVariables"
import { loadPageScriptModule, setPageScriptHotUpdateHandler } from "@/data/studioPageScripts"
import * as globalUtils from "@/utils/globalUtils"
import { getInitialVariableValue, getValueFromObject, setValueInObject } from "@/utils/helpers"
import { isDynamicValue, normalizeDynamicValue } from "@/utils/code"
import { isFunctionExpression, toOptionalChaining, getTopLevelBindings } from "@/utils/parseCode"
import type {
	Filters,
	Resource,
	DocumentResource,
	DocumentListResource,
	APIResource,
	DataResult,
} from "@/types/Studio/StudioResource"
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
	const currentPageName = ref<string | null>(null)
	let pageScriptScope: EffectScope | null = null
	let resourceWatchers: WatchStopHandle[] = []

	function setRouteObject(route: ComputedRef) {
		routeObject.value = route
	}

	function setRouterObject(router: Router | Readonly<Router>) {
		routerObject.value = router
	}

	// RESOURCES
	let pendingResources: Record<string, any> | null = null
	async function setPageResources(
		page: StudioPage,
		setResourceConfig: boolean = false,
		preloadedResources?: Resource[],
	) {
		stopResourceWatchers()
		// Each load uses its own map, so old async updates cannot change the current page resources.
		const pageResources = reactive({}) as Record<string, any>
		pendingResources = pageResources

		let resourceRows = preloadedResources
		if (!resourceRows) {
			studioPageResources.filters = { parent: page.name }
			await studioPageResources.reload()
			if (pendingResources !== pageResources) return
			resourceRows = studioPageResources.data as Resource[]
		}

		await Promise.all(
			resourceRows.map(async (resource: Resource) => {
				await addPageResource(resource, pageResources)
				const newResource = pageResources[resource.resource_name]
				if (setResourceConfig && newResource) {
					newResource.resource_id = resource.resource_id
					newResource.resource_type = resource.resource_type
				}
			}),
		)

		if (pendingResources === pageResources) {
			resources.value = pageResources
		}
	}

	async function addPageResource(resource: Resource, pageResources: Record<string, any>) {
		switch (resource.resource_type) {
			case "Document":
				return addDocumentResource(resource, pageResources)
			case "Document List":
				pageResources[resource.resource_name] = getListResource(resource)
				break
			case "API Resource":
				pageResources[resource.resource_name] = getAPIResource(resource)
				break
		}
	}

	function getListResource(resource: DocumentListResource) {
		let fields = []
		if ("fields" in resource && typeof resource.fields === "string") {
			fields = JSON.parse(resource.fields)
		}

		const params: any = {
			doctype: resource.document_type,
			fields: fields.length ? fields : "*",
			filters: useDynamicParams(
				() => getEvaluatedFilters(resource.filters),
				(filters) => {
					listResource.update({ filters })
					if (listResource.auto) listResource.reload()
				},
			),
			pageLength: resource.limit,
			auto: resource.auto,
			...getTransforms(resource),
			...getSuccessErrorHandlers(resource),
		}
		if (resource.sort_field) {
			params["orderBy"] = `${resource.sort_field} ${resource.sort_order}`
		}
		const listResource = createListResource(params)
		// initialize listResource.data to an empty array to avoid undefined errors in the UI, frappe-ui sets data to null by default
		listResource.data = []
		return listResource
	}

	function getAPIResource(resource: APIResource) {
		const apiResource = createResource({
			url: resource.url,
			method: resource.method,
			params: useDynamicParams(
				() => getAPIParams(resource.params),
				(params) => {
					apiResource.update({ params })
					if (apiResource.auto) apiResource.reload()
				},
			),
			auto: resource.auto,
			...getTransforms(resource),
			...getSuccessErrorHandlers(resource),
		})
		return apiResource
	}

	const addDocumentResource = async (resource: DocumentResource, pageResources: Record<string, any>) => {
		const params = {
			doctype: resource.document_type,
			auto: resource.auto,
			...getTransforms(resource),
			...getSuccessErrorHandlers(resource),
			...getWhitelistedMethods(resource),
		}

		if (!resource.fetch_document_using_filters || !resource.filters) {
			pageResources[resource.resource_name] = createDocumentResource({ ...params, name: resource.document_name })
			return
		}

		// The docname can't change on an existing document resource (frappe-ui caches them by
		// doctype+name), so a filter change means re-resolving the docname and replacing the entry.
		// loadDoc is the entry's only writer; latestRequest keeps only the newest lookup's result.
		let latestRequest = 0
		async function loadDoc(currentFilters: Filters) {
			const request = ++latestRequest
			const docname = await resolveDocnameFromFilters(resource, currentFilters)
			if (request !== latestRequest) return
			if (!docname) {
				pageResources[resource.resource_name] = undefined
				return
			}
			const doc = createDocumentResource({ ...params, name: docname })
			// carry over the editor's config stamps (see setResourceConfig in setPageResources)
			const oldDoc = pageResources[resource.resource_name]
			if (oldDoc?.resource_id) {
				doc.resource_id = oldDoc.resource_id
				doc.resource_type = oldDoc.resource_type
			}
			pageResources[resource.resource_name] = doc
		}

		const filters = useDynamicParams(() => getEvaluatedFilters(resource.filters) || {}, loadDoc)
		await loadDoc(filters)
	}

	// Evaluate a resource's dynamic input ({{ }} filters/params) and return the initial value,
	// then call onChange whenever a route/variable change alters the result
	function useDynamicParams<T>(evaluate: () => T, onChange: (value: T) => void): T {
		const evaluated = computed(evaluate)
		const stop = watch(
			() => JSON.stringify(evaluated.value),
			() => onChange(evaluated.value),
		)
		resourceWatchers.push(stop)
		return evaluated.value
	}

	const getEvaluatedFilters = (filters: Filters | null = null) => {
		if (!filters) return
		if (typeof filters === "string") {
			filters = JSON.parse(filters)
		}

		const evaluatedFilters: Filters = {}

		for (const key in filters) {
			const raw = filters[key]
			if (Array.isArray(raw)) {
				// A list filter is [operator, value] and Frappe unpacks exactly that pair —
				// the operator must survive to the wire (stripping it turned "!=" and
				// "not in" filters into equality/bare lists). A flat [op, v1, v2, ...] is
				// a malformed multi-value filter from older saves — recover it.
				const operator = raw[0]
				const value = raw.length > 2 ? raw.slice(1) : raw[1]
				const evaluated = evaluateFilterValue(value)
				evaluatedFilters[key] = evaluated === undefined ? undefined : [operator, evaluated]
			} else {
				evaluatedFilters[key] = evaluateFilterValue(raw)
			}
		}

		return evaluatedFilters
	}

	const evaluateFilterValue = (value: any): any => {
		if (Array.isArray(value)) {
			return value.map((item) => evaluateFilterValue(item)).filter((item) => item !== undefined)
		}
		if (isDynamicValue(value)) {
			// null ?? undefined → undefined, so nullish filters get dropped on serialization
			return getDynamicValue(value, {}) ?? undefined
		}
		return value
	}

	function getAPIParams(params: Record<string, any> | string | null = null) {
		if (!params) return null
		if (typeof params === "string") {
			params = JSON.parse(params)
		}
		// evaluate on a copy: evaluation re-runs on every context change and must not bake values into the config
		const evaluated: Record<string, any> = { ...(params as Record<string, any>) }
		Object.entries(evaluated).forEach(([key, value]) => {
			if (isDynamicValue(value)) {
				// null ?? undefined → undefined, so nullish params get dropped on serialization
				evaluated[key] = getDynamicValue(value, {}) ?? undefined
			}
		})
		return evaluated
	}

	const resolveDocnameFromFilters = async (resource: DocumentResource, filters: Filters) => {
		// the common `name = {{ route.params.id }}` case resolves to the docname itself — no server lookup needed
		const keys = Object.keys(filters)
		if (keys.length === 1 && keys[0] === "name") {
			return filters.name
		}
		// other filters (e.g. category = tech) need a lookup for one matching doc's name
		const doc = await call("frappe.client.get_value", {
			doctype: resource.document_type,
			fieldname: "name",
			filters,
		})
		return doc?.name
	}

	const getTransforms = (resource: Resource) => {
		if (!resource.transform) return {}
		return {
			transform: (data: any) => {
				try {
					const context = { ...scriptContext.value, data }
					const transformFn = new Function(
						"ctx",
						`with(ctx) {
							${resource.transform}
							return transform(data);
						}`,
					)
					return transformFn(context)
				} catch (error) {
					console.error(`Error executing transform: ${resource.transform}`, error)
					return data
				}
			},
		}
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

	function stopResourceWatchers() {
		resourceWatchers.forEach((stop) => stop())
		resourceWatchers = []
	}

	function teardownPage() {
		stopResourceWatchers()
		disposePageScriptScope()
	}

	// VARIABLES
	async function setPageVariables(page: StudioPage, preloadedVariables?: Variable[]) {
		let variableRows = preloadedVariables
		if (!variableRows) {
			studioVariables.filters = { parent: page.name }
			await studioVariables.reload()
			variableRows = studioVariables.data as Variable[]
		}
		variables.value = {}

		variableRows.map((variable: Variable) => {
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

	// PAGE SCRIPT
	async function setPageScript(page: StudioPage, isStandardPage: boolean = false) {
		disposePageScriptScope()
		pageScriptBindings.value = {}
		pageScriptError.value = null
		currentPageName.value = page.name

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

	function disposePageScriptScope() {
		pageScriptScope?.stop()
		pageScriptScope = null
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

	function reportPageScriptError(error: unknown) {
		console.error("Error running page script", error)
		pageScriptError.value = error instanceof Error ? error.message : String(error)
	}

	// HMR: the active page's script (or a composable/util it imports) was edited. Re-run its setup
	// with the freshly hot-loaded module so new refs/computed and changed dependency code take
	// effect without a reload. (Pinia stores keep their singleton state — they refresh their code
	// only via their own acceptHMRUpdate.) Registered once here so both the editor and the preview
	// (each with their own codeStore) hot-apply script edits to the page they're showing.
	async function applyPageScriptHMR(setup: unknown) {
		pageScriptError.value = null
		pageScriptBindings.value = await runPageScriptSetup(setup)
	}
	setPageScriptHotUpdateHandler((pageName, setup) => {
		if (currentPageName.value === pageName) applyPageScriptHMR(setup)
	})

	// SCRIPT CONTEXTS
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

	// Base context for every script scope — event/success/error handlers, function-value props, and page-script setup
	const scriptContext = computed(() => {
		const variablesRefs = toRefs(variables.value)
		// Resources and currentRoute are proxies so scripts can destructure them once and still see the current values
		return {
			...variablesRefs,
			...currentResourceProxies(),
			...pageScriptBindings.value,
			...globalUtils,
			route: currentRoute,
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

	const resourceProxies: Record<string, any> = {}
	function currentResourceProxies() {
		const proxies: Record<string, any> = {}
		for (const name in resources.value) {
			resourceProxies[name] ??= proxyToCurrent(() => resources.value[name])
			proxies[name] = resourceProxies[name]
		}
		return proxies
	}

	const currentRoute = proxyToCurrent(() => unref(routeObject.value))

	function proxyToCurrent(getCurrent: () => any) {
		return new Proxy(
			{},
			{
				get: (_, key) => getCurrent()?.[key],
				has: (_, key) => key in (getCurrent() || {}),
				set: (_, key, value) => {
					const target = getCurrent()
					if (target) target[key] = value
					return true
				},
				ownKeys: () => Reflect.ownKeys(getCurrent() || {}),
				getOwnPropertyDescriptor: (_, key) => {
					const target = getCurrent()
					if (target && key in target) return { enumerable: true, configurable: true, value: target[key] }
				},
			},
		)
	}

	// EXPRESSION EVALUATION
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

			if (dynamicValue !== null && typeof dynamicValue === "object") {
				// for proptype as object, return the evaluated object as is
				// TODO: handle this more explicitly by checking the actual prop type
				return dynamicValue
			}

			// If the whole value is a single dynamic expression, return the normalized evaluated value
			// e.g. value === "{{ showTooltip }}" should return boolean true/false if appropriate
			if (value.trim().match(/^\{\{.*\}\}$/)) {
				return normalizeDynamicValue(dynamicValue)
			}

			// Append the static part of the string
			result += value.slice(lastIndex, match.index)
			// Append the evaluated dynamic value, treating null/undefined as empty
			result += dynamicValue != null ? String(dynamicValue) : ""
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

	// EVENT SCRIPTS
	function executeUserScript(
		script: string,
		slotScope?: Record<string, any>,
		componentContext?: Record<string, any>,
		eventArgs?: any[],
	) {
		try {
			const context = { ...scriptContext.value, ...slotScope, ...componentContext, eventArgs }

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
		slotScope?: Record<string, any>,
		componentContext?: Record<string, any>,
		eventArgs?: any[],
	) {
		try {
			const context = {
				...scriptContext.value,
				...slotScope,
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
		slotScope?: Record<string, any>,
		componentContext?: Record<string, any>,
		eventArgs?: any[],
	) {
		try {
			const context = {
				...scriptContext.value,
				...slotScope,
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

	return {
		setRouteObject,
		setRouterObject,
		routeObject,
		routerObject,
		// resources
		resources,
		setPageResources,
		teardownPage,
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
