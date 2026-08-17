import { computed, unref, isRef } from "vue"
import useCodeStore from "@/stores/codeStore"
import type { CompletionSource } from "@/types"
import { isPrivateKey } from "@/utils/helpers"
import { getBindingType } from "@/utils/parseCode"
import { getCompletions } from "./autocompletions"
import { vueApiSources } from "./vueApiCompletions"
import type { CompletionContext, CompletionSource as CMCompletionSource } from "@codemirror/autocomplete"
import { syntaxTree } from "@codemirror/language"
import type { SyntaxNode } from "@lezer/common"
import * as globalUtils from "@/utils/globalUtils"

export const useStudioCompletions = (canEditValues: boolean = false, includeVueApis: boolean = false) => {
	const codeStore = useCodeStore()

	const completionSources = computed(() => {
		const sources: CompletionSource[] = []
		Object.entries(codeStore.variables || {}).forEach(([variable, item]) => {
			// When canEditValues is true, variables are refs (toRefs)
			const wrappedItem = canEditValues ? { value: item } : item
			sources.push({
				item: wrappedItem,
				completion: {
					label: variable,
					type: "variable",
					detail: "Variable",
					apply(view, completion, from, to) {
						let insertText = canEditValues ? `${completion.label}.value` : `${completion.label}`
						view.dispatch({
							changes: { from, to, insert: insertText },
						})
					},
				}
			})
		})

		Object.entries(codeStore.resources || {}).forEach(([resource, item]) => {
			sources.push({
				item,
				completion: {
					label: resource,
					type: "data",
					detail: "Data Source",
				}
			})
		})

		sources.push({
			item: codeStore.routeObject?.value,
			completion: {
				label: "route",
				type: "variable",
				detail: "Vue Router Route",
			}
		})

		sources.push({
			item: codeStore.routerObject,
			completion: {
				label: "router",
				type: "variable",
				detail: "Vue Router Object",
			}
		})

		if (window.studio) {
			Object.entries(window.studio).forEach(([funcName, func]) => {
				if (isPrivateKey(funcName)) {
					return
				}

				sources.push({
					item: func,
					completion: {
						label: funcName,
						type: "function",
						detail: "Utility Function",
						apply(view, completion, from, to) {
							let insertText = `studio.${completion.label}()`
							view.dispatch({
								changes: { from, to, insert: insertText },
								selection: { anchor: from + insertText.length - 1 } // Place cursor inside the parentheses
							})
						}
					}
				})
			})
		}

		Object.entries(codeStore.pageScriptBindings || {}).forEach(([name, binding]) => {
			const unwrapped = unref(binding)
			const isFunction = typeof unwrapped === "function"
			const refLike = isRef(binding)
			const detail = getBindingType(binding)
			// In script context, surface a ref as `{ value }` so `name.value` member completion works.
			const item = canEditValues && refLike ? { value: unwrapped } : unwrapped
			sources.push({
				item,
				completion: {
					label: name,
					type: isFunction ? "function" : "variable",
					detail,
					apply(view, completion, from, to) {
						let insertText = completion.label as string
						if (isFunction) insertText = `${insertText}()`
						else if (canEditValues && refLike) insertText = `${insertText}.value`
						const cursorPos = isFunction ? from + insertText.length - 1 : from + insertText.length
						view.dispatch({
							changes: { from, to, insert: insertText },
							selection: { anchor: cursorPos },
						})
					},
				},
			})
		})

		Object.entries(globalUtils).forEach(([funcName, func]) => {
			if (isPrivateKey(funcName)) {
				return
			}

			sources.push({
				item: func,
				completion: {
					label: funcName,
					type: "function",
					detail: "Utility Function",
					apply(view, completion, from, to) {
						let insertText = typeof func === "function" ? `${completion.label}()` : `${completion.label}`
						// Place cursor inside the parentheses if function
						let cursorPos = typeof func === "function" ? from + insertText.length - 1 : from + insertText.length
						view.dispatch({
							changes: { from, to, insert: insertText },
							selection: { anchor: cursorPos }
						})
					}
				}
			})
		})

		// Only the interpreted page script has the Vue reactivity APIs injected into its scope; other
		// editors (event/callback/transform handlers, dynamic-value expressions) don't.
		if (includeVueApis) {
			sources.push(...vueApiSources())
		}

		return sources
	})

	return (context: CompletionContext, customSources: CompletionSource[] = []) => {
		return getCompletions(context, [...completionSources.value, ...customSources])
	}
}

// For static prop values (code/array fieldtypes): completion sources that only fire inside the
// contexts evaluated at render time — {{ }} expressions and inline function values. Window globals
// are included since those contexts evaluate in the normal scope chain.
export const useDynamicValueCompletions = () => {
	const getStudioCompletions = useStudioCompletions()

	return (getCustomSources: () => CompletionSource[] | undefined = () => []): CMCompletionSource[] => [
		(context) => {
			if (!isInsideDynamicContext(context)) return null
			return getStudioCompletions(context, getCustomSources() ?? [])
		},
		(context) => {
			if (!isInsideDynamicContext(context)) return null
			return getWindowCompletions(context)
		},
	]
}

const isInsideDynamicContext = (context: CompletionContext) => {
	return isInsideDynamicValue(context) || isInsideFunctionExpression(context)
}

export const isInsideDynamicValue = (context: CompletionContext) => {
	const textBeforeCursor = context.state.doc.sliceString(0, context.pos)
	const lastOpening = textBeforeCursor.lastIndexOf("{{")
	if (lastOpening === -1) return false
	return textBeforeCursor.lastIndexOf("}}") < lastOpening
}

// matches the function-expression prop values evaluated by stringToFunction at render time
const FUNCTION_NODE_NAMES = ["ArrowFunction", "FunctionExpression", "FunctionDeclaration"]

export const isInsideFunctionExpression = (context: CompletionContext) => {
	let node: SyntaxNode | null = syntaxTree(context.state).resolveInner(context.pos, -1)
	while (node) {
		if (FUNCTION_NODE_NAMES.includes(node.name)) return true
		node = node.parent
	}
	return false
}

let windowCompletionSource: CMCompletionSource | null = null

const getWindowCompletions = async (context: CompletionContext) => {
	if (!windowCompletionSource) {
		// dynamic import to keep lang-javascript out of the main bundle, matching Code.vue
		const { scopeCompletionSource } = await import("@codemirror/lang-javascript")
		windowCompletionSource = scopeCompletionSource(window)
	}
	const result = await windowCompletionSource(context)
	if (!result) return null
	return { ...result, options: result.options.filter((option) => !isPrivateKey(option.label)) }
}
