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
