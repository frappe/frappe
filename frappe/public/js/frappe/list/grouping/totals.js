/** The field that holds each document's own currency for the amount `df`; null for an amount in one currency. */
export function get_currency_field(doctype, df) {
	const own = df.fieldtype === "Currency" && frappe.meta.has_field(doctype, df.options);
	return own ? df.options : null;
}

/** An amount in each document's own currency adds up its company-currency field of the same label. */
export function get_total_field(doctype, df) {
	if (!get_currency_field(doctype, df)) return df;
	const label = (f) => (f.label || "").replace(/\s*\([^)]*currency[^)]*\)\s*$/i, "");
	return (
		frappe
			.get_meta(doctype)
			.fields.find(
				(f) =>
					f.fieldtype === "Currency" &&
					f.options?.includes(":") &&
					label(f) === label(df) &&
					frappe.views.ListView.can_read_field(doctype, f)
			) || df
	);
}

/** The column whose total groups rank by: the first one in one currency, since rupees and dollars don't compare. */
export function get_ranked_field(doctype, dfs, totals) {
	return dfs.find(
		(df) => totals[df.fieldname] && !get_currency_field(doctype, get_total_field(doctype, df))
	);
}

/** For options like "Company:company:default_currency": the list's one company, else the user's default. */
export function get_currency_doc(df, filters = []) {
	const link = (df.options || "").split(":")[1];
	if (!link) return {};
	const value = filters.find((filter) => filter[1] === link && filter[2] === "=")?.[3];
	return { [link]: value || frappe.defaults.get_user_default(link) };
}
