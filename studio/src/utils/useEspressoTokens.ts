import resolveConfig from "tailwindcss/resolveConfig"
import tailwindConfig from "../../tailwind.config.js"
import { computed } from "vue"

const designTokens = resolveConfig(tailwindConfig).theme

export const useEspressoTokens = (property: "backgroundColor" | "borderColor" | "color" | "boxShadow" | "borderRadius" | "textColor") => {
	const colors = computed(() => {
		const boxShadow = Object.keys(designTokens?.boxShadow || {}).map((key) => {
			if (!key) return
			return {
				label: key,
				value: designTokens?.boxShadow?.[key as keyof typeof designTokens.boxShadow],
			}
		})

		const borderRadius = Object.keys(designTokens?.borderRadius || {}).map((key) => {
			if (!key) return
			return {
				label: key,
				value: designTokens?.borderRadius?.[key as keyof typeof designTokens.borderRadius],
			}
		})

		const surfaceColors = designTokens?.backgroundColor?.surface as Record<string, string> | undefined
		const backgroundColor = Object.keys(surfaceColors || {}).map((key) => {
			if (!key) return
			return {
				label: key,
				value: (surfaceColors)?.[key],
			}
		})

		const borderColors = designTokens?.borderColor?.outline as Record<string, string> | undefined
		const borderColor = Object.keys(borderColors || {}).map((key) => {
			if (!key) return
			return {
				label: key,
				value: (borderColors)?.[key],
			}
		})

		const textColors = designTokens?.textColor?.ink as Record<string, string> | undefined
		const textColor = Object.keys(textColors || {}).map((key) => {
			if (!key) return
			return {
				label: key,
				value: (textColors)?.[key],
			}
		})

		return {
			backgroundColor: backgroundColor,
			borderColor: borderColor,
			color: textColor,
			textColor: textColor,
			boxShadow: boxShadow,
			borderRadius: borderRadius,
		}
	})

	return colors.value[property]
}
