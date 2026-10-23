import type { BlockStyleMap } from "@/types"
import { kebabToCamelCase } from "@/utils/helpers"

// rawStyles were dropped in favour of baseStyles; older blocks still carry them
export function mergeLegacyRawStyles(baseStyles: BlockStyleMap, rawStyles?: BlockStyleMap) {
	if (!rawStyles) return baseStyles
	Object.entries(rawStyles).forEach(([style, value]) => {
		if (value === null || value === "" || value === undefined) return
		// custom properties (--card-color) are case-sensitive identifiers, never camelCased
		const property = style.startsWith("--") ? style : kebabToCamelCase(style)
		baseStyles[property] = value
	})
	return baseStyles
}
