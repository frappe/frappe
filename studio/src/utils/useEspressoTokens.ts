import resolveConfig from "tailwindcss/resolveConfig"
import tailwindConfig from "../../tailwind.config.js"
import { computed } from "vue"
import { objToArray } from "@/utils/helpers.js"

const designTokens = resolveConfig(tailwindConfig).theme

export const useEspressoTokens = (
	property:
		| "backgroundColor"
		| "borderColor"
		| "boxShadow"
		| "borderRadius"
		| "textColor"
		| "fontSize"
		| "fontWeight"
		| "lineHeight"
		| "letterSpacing",
) => {
	const colors = computed(() => {
		const fontSizes = Object.keys(designTokens?.fontSize || {}).map((key) => {
			if (!key) return
			return {
				label: key,
				value: `text-${key}`,
			}
		})

		return {
			backgroundColor: objToArray(
				designTokens?.backgroundColor?.surface as Record<string, string> | undefined,
			),
			borderColor: objToArray(designTokens?.borderColor?.outline as Record<string, string> | undefined),
			textColor: objToArray(designTokens?.textColor?.ink as Record<string, string> | undefined),
			boxShadow: objToArray(designTokens?.boxShadow),
			borderRadius: objToArray(designTokens?.borderRadius),
			fontSize: fontSizes,
			fontWeight: objToArray(designTokens?.fontWeight),
			lineHeight: objToArray(designTokens?.lineHeight),
			letterSpacing: objToArray(designTokens?.letterSpacing),
		}
	})

	return colors.value[property]
}
