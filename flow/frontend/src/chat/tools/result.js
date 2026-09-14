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

// The same text, unfolded: the callback serializes a return to one JSON line.
export function pretty(content) {
	if (!content) return "";
	try {
		return JSON.stringify(JSON.parse(content), null, 2);
	} catch {
		return content;
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

function blank(value) {
	return value == null || value === "" || (Array.isArray(value) && !value.length);
}

export function cellText(value) {
	if (value == null) return "";
	if (Array.isArray(value)) return `${value.length} ${value.length === 1 ? "row" : "rows"}`;
	if (typeof value === "object") return JSON.stringify(value);
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
