import defaultTheme from "tailwindcss/defaultTheme"
import { computed } from "vue"
import { objToArray } from "@/utils/helpers.js"
import { generateSemanticColors, borderRadius, boxShadow, fontSize } from "frappe-ui/tailwind/tokens.js"

const semanticColors = generateSemanticColors()

const designTokens = {
	backgroundColor: semanticColors.surface,
	borderColor: semanticColors.outline,
	textColor: semanticColors.ink,
	boxShadow: boxShadow,
	borderRadius: borderRadius,
	fontSize: fontSize,
	fontWeight: defaultTheme.fontWeight,
	lineHeight: defaultTheme.lineHeight,
	letterSpacing: defaultTheme.letterSpacing,
}

const tokens = computed(() => {
	const fontSizes = Object.keys(designTokens?.fontSize || {}).map((key) => {
		if (!key) return
		return {
			label: key,
			value: `text-${key}`,
		}
	})

	return {
		backgroundColor: objToArray(designTokens?.backgroundColor as Record<string, string> | undefined),
		borderColor: objToArray(designTokens?.borderColor as Record<string, string> | undefined),
		textColor: objToArray(designTokens?.textColor as Record<string, string> | undefined),
		boxShadow: objToArray(designTokens?.boxShadow),
		borderRadius: objToArray(designTokens?.borderRadius),
		fontSize: fontSizes,
		fontWeight: objToArray(designTokens?.fontWeight),
		lineHeight: objToArray(designTokens?.lineHeight),
		letterSpacing: objToArray(designTokens?.letterSpacing),
	}
})

export const getEspressoTokens = (
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
	return tokens.value[property]
}
