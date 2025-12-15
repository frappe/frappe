import { FUNCTION_STRING_REGEX } from "@/utils/constants"

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

		// match exactly {{ ... }} (allow whitespace inside)
		if (/^\{\{[\s\S]*\}\}$/.test(unescaped)) {
			return unescaped
		}
		return match
	})
}