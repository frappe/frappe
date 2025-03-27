import { computed } from "vue"
import { SelectOption } from "@/types"

export function useVariables(variables: Record<string, any>) {
	const variableOptions = computed(() => {
		const options: SelectOption[] = []

		function traverse(obj: any, path = "") {
			for (const key in obj) {
				const currentPath = path ? `${path}.${key}` : key
				options.push({ value: currentPath, label: currentPath })

				if (typeof obj[key] === "object" && obj[key] !== null) {
					// add nested properties
					traverse(obj[key], currentPath)
				}
			}
		}

		traverse(variables)
		return options
	})

	return {
		variableOptions
	}
}