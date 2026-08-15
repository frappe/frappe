import defaultTheme from "tailwindcss/defaultTheme"
import { computed } from "vue"
import { objToArray } from "@/utils/helpers.js"
import {
	borderRadius,
	boxShadow,
	fontSize,
	generateCSSVariables,
	generateSemanticColors,
} from "frappe-ui/tailwind/tokens.js"

// frappe-ui exposes semantic colors as { category: { name: cssValue } }. Use the names and reference the CSS variable its plugin defines on :root. The
// resolved light value is baked in as a fallback (var(--surface-base, #ffffff)),
// exactly like frappe-ui's own utilities, so the color still renders in contexts that don't load frappe-ui's stylesheet (e.g. exported markup).
const semanticColors = generateSemanticColors()
const lightVars: Record<string, string> = generateCSSVariables()[":root"]

const toColorOptions = (category: "surface" | "outline" | "ink") =>
	Object.keys(semanticColors[category]).map((name) => {
		const variable = `--${category}-${name}`
		const fallback = lightVars[variable]
		return {
			label: name,
			value: fallback ? `var(${variable}, ${fallback})` : `var(${variable})`,
		}
	})

const designTokens = {
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
		backgroundColor: toColorOptions("surface"),
		borderColor: toColorOptions("outline"),
		textColor: toColorOptions("ink"),
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
