import { computed, unref, isRef } from "vue"
import useCodeStore from "@/stores/codeStore"
import type { CompletionSource } from "@/types"
import { isPrivateKey } from "@/utils/helpers"
import { getBindingType } from "@/utils/parseCode"
import { getCompletions } from "./autocompletions"
import { vueApiSources } from "./vueApiCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"
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