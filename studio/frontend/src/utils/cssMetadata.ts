import cssPropertyMetadata from "@/data/cssPropertyMetadata.json"
import { camelToKebabCase } from "@/utils/helpers"
import { BORDER_UNIT_OPTIONS, DIMENSION_UNIT_OPTIONS } from "@/utils/unitOptions"

// see scripts/generate-css-property-metadata.mjs
type CSSPropertyMetadata = {
	kind: "color" | "length" | "integer" | "number" | "keyword"
	keywords?: string[]
	baseline?: boolean
}

type Option = { label: string; value: string }

// props for InlineInput (type/options/enableSlider/unitOptions/...)
type StyleControlProps = Record<string, unknown>

const MAX_SEARCH_RESULTS = 50

const metadata = cssPropertyMetadata as Record<string, CSSPropertyMetadata>

const baselineCSSProperties = Object.keys(metadata).filter((property) => metadata[property].baseline)

const cssPropertyNamePattern = /^-?[a-z][a-z0-9-]*$/

const isValidCSSPropertyName = (property: string) => cssPropertyNamePattern.test(property)

const normalizeCSSPropertyName = (property: string | null | undefined) =>
	camelToKebabCase((property || "").trim()).toLowerCase()

const getKeywordOptions = (property: string): Option[] =>
	(metadata[property]?.keywords || []).map((keyword) => ({ label: keyword, value: keyword }))

const keywordControl = (property: string): StyleControlProps => {
	const options = getKeywordOptions(property)
	if (!options.length) return {}
	return {
		type: "autocomplete",
		options,
		showInputAsOption: true,
	}
}

// properties whose inferred control is not the one the editor wants
const propertySpecificControls: Record<string, () => StyleControlProps> = {
	opacity: () => ({
		type: "autocomplete",
		options: ["0", "0.25", "0.5", "0.75", "1"].map((value) => ({ label: value, value })),
		showInputAsOption: true,
	}),
}

const controlsByKind: Record<CSSPropertyMetadata["kind"], (property: string) => StyleControlProps> = {
	color: () => ({ type: "color" }),
	length: (property) => ({
		...keywordControl(property),
		enableSlider: true,
		unitOptions: property.includes("border") ? BORDER_UNIT_OPTIONS : DIMENSION_UNIT_OPTIONS,
	}),
	integer: (property) => ({ ...keywordControl(property), enableSlider: true }),
	// unitless by and large (opacity, flex-grow, ...), so no unit options
	number: (property) => ({ ...keywordControl(property), enableSlider: true }),
	keyword: (property) => keywordControl(property),
}

const controlCache = new Map<string, StyleControlProps>()

const buildControl = (property: string) => {
	const buildSpecificControl = propertySpecificControls[property]
	if (buildSpecificControl) return buildSpecificControl()
	const kind = metadata[property]?.kind
	return kind ? controlsByKind[kind](property) : {}
}

const getCSSPropertyControl = (property: string) => {
	if (!controlCache.has(property)) {
		controlCache.set(property, buildControl(property))
	}
	return controlCache.get(property) as StyleControlProps
}

const normalizeSearchText = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, "")

const getFuzzySearchScore = (query: string, property: string) => {
	const normalizedQuery = query.toLowerCase()
	const compactQuery = normalizeSearchText(query)
	const compactProperty = normalizeSearchText(property)

	if (!compactQuery) return 0
	if (property.includes(normalizedQuery)) return property.indexOf(normalizedQuery)
	if (compactProperty.includes(compactQuery)) return 25 + compactProperty.indexOf(compactQuery)

	let score = 100
	let previousIndex = -1

	for (const character of compactQuery) {
		const index = compactProperty.indexOf(character, previousIndex + 1)
		if (index === -1) return null

		const gap = index - previousIndex - 1
		score += gap * 2
		previousIndex = index
	}

	return score + compactProperty.length - compactQuery.length
}

const getCSSPropertyOptions = (query: string, excludedProperties = new Set<string>()) => {
	const normalizedQuery = query.trim().toLowerCase()
	const availableProperties = baselineCSSProperties.filter((property) => !excludedProperties.has(property))

	if (!normalizedQuery) {
		return availableProperties
			.slice(0, MAX_SEARCH_RESULTS)
			.map((property) => ({ label: property, value: property }))
	}

	return availableProperties
		.map((property) => ({ property, score: getFuzzySearchScore(normalizedQuery, property) }))
		.filter((result): result is { property: string; score: number } => result.score !== null)
		.sort((a, b) => a.score - b.score || a.property.localeCompare(b.property))
		.slice(0, MAX_SEARCH_RESULTS)
		.map(({ property }) => ({ label: property, value: property }))
}

export {
	getCSSPropertyControl,
	getCSSPropertyOptions,
	isValidCSSPropertyName,
	normalizeCSSPropertyName,
}
