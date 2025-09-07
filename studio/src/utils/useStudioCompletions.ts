import { computed } from "vue"
import useStudioStore from "@/stores/studioStore"
import type { CompletionSource } from "@/types"
import { getCompletions } from "./autocompletions"
import type { CompletionContext } from "@codemirror/autocomplete"

export const useStudioCompletions = (canEditValues: boolean = false) => {
	const store = useStudioStore()

	const completionSources = computed(() => {
		const sources: CompletionSource[] = []
		Object.entries(store.variables || {}).forEach(([variable, item]) => {
			sources.push({
				item,
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

		Object.entries(store.resources || {}).forEach(([resource, item]) => {
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
			item: store.routeObject,
			completion: {
				label: "route",
				type: "variable",
				detail: "Vue Router Route",
			}
		})

		if (window.studio) {
			Object.entries(window.studio).forEach(([funcName, func]) => {
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

		return sources
	})

	return (context: CompletionContext, customSources: CompletionSource[] = []) => {
		return getCompletions(context, [...completionSources.value, ...customSources])
	}
}