import resolveConfig from "tailwindcss/resolveConfig"
import tailwindConfig from "../../tailwind.config.js"
import { computed } from "vue"

const designTokens = resolveConfig(tailwindConfig).theme

export const useEspressoTokens = (property: "backgroundColor" | "borderColor" | "color") => {
	const colors = computed(() => {
		return {
			backgroundColor: designTokens?.backgroundColor?.surface,
			borderColor: designTokens?.borderColor?.outline,
			color: designTokens?.textColor?.ink,
		}
	})

	return colors.value[property]
}
