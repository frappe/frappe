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