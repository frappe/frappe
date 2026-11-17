import {
	DYNAMIC_EXPRESSION_REGEX,
	QUOTED_STRING_CONTENT_REGEX,
} from "@/utils/constants"
import { isFunctionExpression } from "@/utils/parseCode"

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
	return json5String.replace(QUOTED_STRING_CONTENT_REGEX, (match, content) => {
		const unescaped = unescape(content)
		if (isFunctionExpression(unescaped)) {
			return unescaped
		}
		return match
	})
}

export function unquoteDynamicExpressions(json5String: string) {
	/* Unquote quoted strings that are exactly a single dynamic expression: "{{ ... }}" */
	return json5String.replace(QUOTED_STRING_CONTENT_REGEX, (match, content) => {
		const unescaped = unescape(content)
		if (DYNAMIC_EXPRESSION_REGEX.test(unescaped)) {
			return unescaped
		}
		return match
	})
}

function unescape(str: string) {
	return str
		.replace(/\\(\\|n|t|")/g, (match, content) => {
			const map: Record<string, string> = {
				n: "\n",
				t: "\t",
				'"': '"',
				"\\": "\\",
			}
			return map[content] || match
		})
		.trim()
}