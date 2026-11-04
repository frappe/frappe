import {
	ref, computed, watch, watchEffect, reactive, toRef, toRefs, unref,
	isRef, isReactive, shallowRef, readonly, markRaw, nextTick,
	onMounted, onBeforeMount, onBeforeUnmount, onUnmounted,
	type ComputedRef, type WatchStopHandle, h,
} from "vue"
import { watchDebounced } from "@vueuse/core"
import { createDocumentResource, createListResource, createResource, call } from "frappe-ui"
import { studioPageResources } from "@/data/studioResources"
import { studioVariables } from "@/data/studioVariables"
import { hasPageScript, loadPageScriptModule } from "@/data/studioPageScripts"
import { loadAppPageScriptModule } from "@/runtime/appRuntime"
import * as globalUtils from "@/utils/globalUtils"
import { useSocket } from "@/socket"
import { getInitialVariableValue, getValueFromObject, setValueInObject } from "@/utils/helpers"
import { isDynamicValue, normalizeDynamicValue } from "@/utils/code"
import { DYNAMIC_EXPRESSION_CONTENT_REGEX } from "@/utils/constants"
import { isFunctionExpression, toOptionalChaining } from "@/utils/parseCode"
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
import type { Ref } from "vue"
import type { Router, RouteLocationNormalized } from "vue-router"

// What a page script may import from vue — the list the script editor offers
export const pageScriptVueApis = {
	ref, reactive, computed, watch, watchEffect, watchDebounced,
	toRef, toRefs, unref, isRef, isReactive,
	shallowRef, readonly, markRaw, nextTick,
	onMounted, onBeforeMount, onBeforeUnmount, onUnmounted,
}

// One page's data: resources, variables, page script and the contexts bindings evaluate against
export function createPageScope(
	routeObject: Ref<ComputedRef | RouteLocationNormalized | undefined>,
	routerObject: Ref<Router | Readonly<Router> | undefined>,
) {
	const resources = ref<Record<string, Resource>>({})
	const variables = ref<Record<string, any>>({})

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
	const pageSetup = shallowRef<Function | null>(null)
	const pageScriptVersion = ref(0)
	const pageScriptReady = ref(false)
	let resourceWatchers: WatchStopHandle[] = []

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
		async function loadDoc(currentFilters: Partial<Filters>) {
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

		const evaluatedFilters: Partial<Filters> = {}

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

	const resolveDocnameFromFilters = async (resource: DocumentResource, filters: Partial<Filters>) => {
		// the common `name = {{ route.params.id }}` case resolves to the docname itself — no server lookup needed
		const keys = Object.keys(filters)
		if (keys.length === 1 && keys[0] === "name") {
			const name = filters.name as unknown
			if (typeof name === "string") return name
			if (Array.isArray(name) && name[0] === "=") return name[1]
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
		// drops the script as well: the host unmounts the instance running it, which is what stops
		// its hooks and effects
		setPageSetup(null)
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
	// Every page script is a `setup(context)` module. A build compiles it ahead of time and the
	// runtime loads it by page name; without one it compiles in the browser from page.script.
	// Loading only fetches the module. PageScriptHost calls setup() from its own component
	// setup(), so the script runs in a real component instance like any Vue page's does.
	async function loadPageScript(page: StudioPage) {
		currentPageName.value = page.name
		try {
			setPageSetup((await loadPageSetupModule(page))?.default)
		} catch (error) {
			setPageSetup(null)
			reportPageScriptError(error)
		}
	}

	async function loadPageSetupModule(page: StudioPage): Promise<Record<string, any> | null> {
		if (hasPageScript(page.name)) return loadPageScriptModule(page.name)
		if (!page.script?.trim()) return null
		return loadAppPageScriptModule(page)
	}

	// The host is keyed on the version, so a new setup unmounts the instance running the old one
	// — cleaning up its hooks and effects — before a fresh instance runs this one.
	function setPageSetup(setup: unknown) {
		pageSetup.value = typeof setup === "function" ? (setup as Function) : null
		pageScriptBindings.value = {}
		pageScriptError.value = null
		pageScriptReady.value = false
		pageScriptVersion.value++
	}

	// Called by PageScriptHost from its own setup(), where setup(ctx) gets the live execution
	// context (resources/variables/route/router). What the script registers synchronously belongs
	// to the host instance; what it registers after an await does not, as in any async setup().
	function runPageSetup() {
		const setup = pageSetup.value
		const version = pageScriptVersion.value
		if (!setup) return applyPageScriptBindings({}, version)

		try {
			const bindings = setup(scriptContext.value)
			if (bindings instanceof Promise) {
				bindings.then(
					(resolved) => applyPageScriptBindings(resolved, version),
					(error) => failPageScript(error, version),
				)
			} else {
				applyPageScriptBindings(bindings, version)
			}
		} catch (error) {
			failPageScript(error, version)
		}
	}

	// An async setup still running when the script changes must not overwrite the new one's work
	function applyPageScriptBindings(bindings: unknown, version: number) {
		if (version !== pageScriptVersion.value) return
		pageScriptBindings.value = (bindings as Record<string, any>) || {}
		pageScriptReady.value = true
	}

	function failPageScript(error: unknown, version: number) {
		if (version !== pageScriptVersion.value) return
		reportPageScriptError(error)
		pageScriptReady.value = true
	}

	function reportPageScriptError(error: unknown) {
		console.error("Error running page script", error)
		pageScriptError.value = error instanceof Error ? error.message : String(error)
	}

	// HMR: this page's script (or a composable/util it imports) was edited. Swap in the freshly
	// hot-loaded setup; the host remounts and runs it without a reload.
	function applyPageScriptHotUpdate(pageName: string, setup: unknown) {
		if (currentPageName.value !== pageName) return
		setPageSetup(setup)
	}

	// SCRIPT CONTEXTS
	const evalContext = computed(() => {
		return {
			...variables.value,
			...resources.value,
			...pageScriptTemplateBindings.value,
			...globalUtils,
			socket: useSocket(),
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
			socket: useSocket(),
			route: currentRoute,
			router: routerObject.value,
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
		const matches = value.matchAll(DYNAMIC_EXPRESSION_CONTENT_REGEX)

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
			if (match[0] === value.trim()) {
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

	return reactive({
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
		pageScriptVersion,
		pageScriptReady,
		loadPageScript,
		runPageSetup,
		applyPageScriptHotUpdate,
		// code execution
		evalContext,
		scriptContext,
		getDynamicValue,
		evaluateDynamicValues,
		executeUserScript,
		handleSuccess,
		handleError,
		getAPIParams,
		stringToFunction,
	})
}

export type PageScope = ReturnType<typeof createPageScope>
