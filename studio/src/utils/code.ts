import { FUNCTION_STRING_REGEX, DYNAMIC_EXPRESSION_REGEX } from "@/utils/constants"

export function isDynamicValue(value: string) {
	// Check if the prop value is a string and contains a dynamic expression
	if (typeof value !== "string") return false
	return value && value.includes("{{") && value.includes("}}")
}

export function normalizeDynamicValue(value: any) {
	/** Normalize evaluated dynamic results. */
	if (typeof value === "boolean") {
		return value
	} else if (typeof value === "string" && (value === "true" || value === "false")) {
		return value === "true"
	}
	return value
}

export function normalizeCode(json5String: string) {
	/* Normalize code by unquoting dynamic expressions & functions making it more readable */
	return unquoteDynamicExpressions(unquoteFunctions(json5String))
}

export function unquoteFunctions(json5String: string) {
	json5String = json5String.replace(/"((?:[^"\\]|\\.)*)"/g, (match, content) => {
		const unescaped = content
			.replace(/\\n/g, '\n')
			.replace(/\\t/g, '\t')
			.replace(/\\"/g, '"')
			.replace(/\\\\/g, '\\')
			.trim()

		if (FUNCTION_STRING_REGEX.test(unescaped)) {
			return unescaped
		}
		return match
	})
	return json5String
}

export function unquoteDynamicExpressions(json5String: string) {
	/* Unquote quoted strings that are exactly a single dynamic expression: "{{ ... }}" */
	return json5String.replace(/"((?:[^"\\]|\\.)*)"/g, (match, content) => {
		const unescaped = content
			.replace(/\\n/g, '\n')
			.replace(/\\t/g, '\t')
			.replace(/\\"/g, '"')
			.replace(/\\\\/g, '\\')
			.trim()

		if (DYNAMIC_EXPRESSION_REGEX.test(unescaped)) {
			return unescaped
		}
		return match
	})
}