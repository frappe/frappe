import { reactive, watch } from "vue"
import { useRoute } from "vue-router"

/**
 * @returns reactive object with route params as strings
 */
export function useRouteParamsAsStrings() {
	const route = useRoute()
	const stringParams = reactive<{ [key: string]: string }>({})

	const updateParams = () => {
		const { params } = route
		for (const [key, value] of Object.entries(params)) {
			if (typeof value === "string") {
				stringParams[key] = value
			}
		}
	}

	watch(route, updateParams, { immediate: true })

	return stringParams
}
