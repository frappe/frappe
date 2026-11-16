/** JSON Schema, limited to the keywords the checker reads. */
export interface ActSchema {
	type?: string | string[];
	description?: string;
	properties?: Record<string, ActSchema>;
	required?: string[];
	additionalProperties?: boolean;
	enum?: unknown[];
	minLength?: number;
	items?: ActSchema;
}

/** Why `value` fails `schema`, in words that say what to send instead; undefined when it passes. */
export function checkValue(schema: ActSchema, value: unknown, path = "value"): string | undefined {
	const kinds = schema.type === undefined ? [] : [schema.type].flat();
	if (kinds.length && !kinds.some((kind) => isKind(kind, value)))
		return `${path} must be ${kinds.map(article).join(" or ")}`;
	if (schema.enum && !schema.enum.includes(value))
		return `${path} must be one of ${schema.enum.map((option) => JSON.stringify(option)).join(", ")}`;
	if (typeof value === "string" && schema.minLength && value.length < schema.minLength)
		return `${path} must not be empty`;
	if (Array.isArray(value) && schema.items) return checkItems(schema.items, value, path);
	if (isObject(value) && (schema.properties || schema.required || schema.additionalProperties === false))
		return checkProperties(schema, value, path);
}

function checkItems(items: ActSchema, values: unknown[], path: string) {
	for (const [index, item] of values.entries()) {
		const failure = checkValue(items, item, `${path}[${index}]`);
		if (failure) return failure;
	}
}

function checkProperties(schema: ActSchema, value: Record<string, unknown>, path: string) {
	const missing = schema.required?.find((key) => value[key] === undefined);
	if (missing) return `${path}.${missing} is required`;
	const known = schema.properties ?? {};
	if (schema.additionalProperties === false) {
		const extra = Object.keys(value).find((key) => !(key in known));
		if (extra) return `${path}.${extra} is not a field; use ${Object.keys(known).join(", ") || "no field"}`;
	}
	for (const [key, property] of Object.entries(known)) {
		if (value[key] === undefined) continue;
		const failure = checkValue(property, value[key], `${path}.${key}`);
		if (failure) return failure;
	}
}

function isKind(kind: string, value: unknown) {
	if (kind === "null") return value === null;
	if (kind === "array") return Array.isArray(value);
	if (kind === "object") return isObject(value);
	if (kind === "integer") return Number.isInteger(value);
	return typeof value === kind;
}

function isObject(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function article(kind: string) {
	return `${/^[aeiou]/.test(kind) ? "an" : "a"} ${kind}`;
}
