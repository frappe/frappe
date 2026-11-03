// Saved filters as [doctype, field, operator, value] rows. Old ones are an object instead,
// e.g. { "status": "Open" } or { "posting_date": ["Timespan", "this week"] }.
export function filter_rows(expression, doctype) {
	const filters = window.frappe.utils.process_filter_expression(expression) || [];
	if (Array.isArray(filters)) return filters;
	return Object.entries(filters).map(([field, value]) => [
		doctype,
		field,
		...(Array.isArray(value) ? value : ["=", value]),
	]);
}

// `@me` in a value is whoever is reading: alone, as `%@me%` for a like match, or in an in list
export function with_session_user(rows) {
	const user = window.frappe.session.user;
	const resolve = (value) => {
		if (value === "@me") return user;
		if (value === "%@me%") return `%${user}%`;
		return value;
	};
	return rows.map((row) => {
		const value = row.at(-1);
		const resolved = Array.isArray(value) ? value.map(resolve) : resolve(value);
		return [...row.slice(0, -1), resolved];
	});
}
