import defaultTheme from "tailwindcss/defaultTheme"
import { computed } from "vue"
import { objToArray } from "@/utils/helpers.js"
import { borderRadius, boxShadow, fontSize } from "frappe-ui/tailwind/tokens.js"

// TODO: frappe-ui should cleanly expose tokens and variables
const semanticColorTokens = {
	surface: [
		"white", "gray-1", "gray-2", "gray-3", "gray-4", "gray-5", "gray-6", "gray-7",
		"red-1", "red-2", "red-3", "red-4", "red-5", "red-6", "red-7",
		"green-1", "green-2", "green-3", "amber-1", "amber-2", "amber-3",
		"blue-1", "blue-2", "blue-3", "orange-1", "violet-1", "cyan-1", "pink-1",
		"menu-bar", "cards", "modal", "selected",
	],
	outline: [
		"white", "gray-1", "gray-2", "gray-3", "gray-4", "gray-5",
		"red-1", "red-2", "red-3", "green-1", "green-2", "amber-1", "amber-2",
		"blue-1", "orange-1", "gray-modals",
	],
	ink: [
		"white", "gray-1", "gray-2", "gray-3", "gray-4", "gray-5", "gray-6", "gray-7", "gray-8", "gray-9",
		"red-1", "red-2", "red-3", "red-4", "green-1", "green-2", "green-3",
		"amber-1", "amber-2", "amber-3", "blue-1", "blue-2", "blue-3",
		"cyan-1", "pink-1", "violet-1", "blue-link",
	],
} as const

const toColorOptions = (category: keyof typeof semanticColorTokens) =>
	semanticColorTokens[category].map((name) => ({
		label: name,
		value: `var(--${category}-${name})`,
	}))

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
