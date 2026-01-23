import resolveConfig from "tailwindcss/resolveConfig"
import tailwindConfig from "../../tailwind.config.js"
import { computed } from "vue"

const designTokens = resolveConfig(tailwindConfig).theme

export const useEspressoTokens = (property: "backgroundColor" | "borderColor" | "color" | "boxShadow") => {
	const colors = computed(() => {
		const boxShadow = Object.keys(designTokens?.boxShadow || {}).map((key) => {
			if (!key) return
			return {
				label: key,
				value: designTokens?.boxShadow?.[key as keyof typeof designTokens.boxShadow],
			}
		})
		return {
			backgroundColor: designTokens?.backgroundColor?.surface,
			borderColor: designTokens?.borderColor?.outline,
			color: designTokens?.textColor?.ink,
			boxShadow: boxShadow,
		}
	})

	return colors.value[property]
}
