import { __ } from "@flow/ui-core/translate.js";

// A client tool's return reaches the browser as the JSON text the callback serialized it
// to, so every view parses it back. Errors keep their plain message.
export function parseResult(result) {
	if (!result || result.is_error) return null;
	try {
		return JSON.parse(result.content ?? "");
	} catch {
		return null;
	}
}

export function deskUrl(doctype, name) {
	const slug = doctype.toLowerCase().replace(/ /g, "-");
	return `/app/${slug}/${encodeURIComponent(name)}`;
}

// Only the fields that carry a value become columns, in the order the records name them:
// a read asks for fields most records leave blank, and a blank column is just width.
export function columnsOf(records) {
	const order = [];
	const filled = new Set();
	for (const record of records) {
		for (const [field, value] of Object.entries(record ?? {})) {
			if (!order.includes(field)) order.push(field);
			if (!blank(value)) filled.add(field);
		}
	}
	const columns = order.filter((field) => filled.has(field));
	return columns.length ? columns : order;
}

export function blank(value) {
	if (value == null || value === "") return true;
	return typeof value === "object" && !Object.keys(value).length;
}

// A value in words: a list by its items, a record by its fields, a child table by its
// count. With `whole`, a table reads a row per line, so nothing stays behind a count.
export function cellText(value, whole = false) {
	if (value == null) return "";
	if (Array.isArray(value)) {
		// an empty list counts like the tables beside it
		if (!value.length || (isTable(value) && !whole))
			return value.length === 1 ? __("1 row") : __("{0} rows", [value.length]);
		return value.map((item) => cellText(item, whole)).join(isTable(value) ? "\n" : ", ");
	}
	if (typeof value === "object")
		return Object.entries(value)
			.map(([field, part]) => `${humanize(field)}: ${cellText(part, whole)}`)
			.join(", ");
	return String(value);
}

export function humanize(fieldname) {
	return fieldname.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// A child table: rows of a record, never a list of scalars.
export function isTable(value) {
	return (
		Array.isArray(value) &&
		value.length > 0 &&
		value.every((row) => row !== null && typeof row === "object" && !Array.isArray(row))
	);
}
