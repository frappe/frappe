import { isValidCSSPropertyName } from "@/utils/cssMetadata"
import { camelToKebabCase } from "@/utils/helpers"
import type { BlockStyleMap } from "@/types"

// styles on a block that no dedicated panel control edits, as kebab-case CSS property names.
// controlledProperties is the union of usedStyleProperties declared in ComponentStyles.vue.
export function getStylePropertiesWithoutControls(
	styleMap: BlockStyleMap,
	controlledProperties: Set<string>,
) {
	const properties = new Set<string>()
	Object.keys(styleMap).forEach((style) => {
		const property = camelToKebabCase(style)
		if (!controlledProperties.has(property) && isValidCSSPropertyName(property)) {
			properties.add(property)
		}
	})
	return properties
}
