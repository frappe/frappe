import { computed } from "vue"
import useStudioStore from "@/stores/studioStore"
import type { CompletionSource } from "@/types"
import { copyObject } from "@/utils/helpers"
import router from "@/router/studio_router"
import { getCompletions } from "./autocompletions"
import type { CompletionContext } from "@codemirror/autocomplete"

export const useStudioCompletions = (canEditValues: boolean = false) => {
	const store = useStudioStore()

	const routeObject = computed(() => {
		if (!store.activePage) return ""

		const newRoute = copyObject(router.currentRoute.value)
		// Extract param names from active page's route (e.g., ["employee", "id"] from "/hr/:employee/:id")
		const paramNames = (store.activePage.route.match(/:\w+/g) || []).map(param => param.slice(1))
		newRoute.params = paramNames.reduce((params, name) => {
			params[name] = ""
			return params
		}, {} as Record<string, string>)

		return newRoute
	})

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
			item: routeObject.value,
			completion: {
				label: "route",
				type: "variable",
				detail: "Vue Router Route",
			}
		})

		return sources
	})

	return (context: CompletionContext, customSources: CompletionSource[] = []) => {
		return getCompletions(context, [...completionSources.value, ...customSources])
	}
}