const KINDS = {
	Check: "check",
	Date: "date",
	Datetime: "date",
	Time: "time",
	Currency: "number",
	Float: "number",
	Int: "number",
	Percent: "number",
	Rating: "number",
	Duration: "number",
	Select: "values",
	Link: "values",
	Autocomplete: "values",
};

/** Which picker a field gets: values, date, time, number, check or text. */
export function kind_of(df) {
	// an Autocomplete whose options a script fills has none to list
	if (df.fieldtype === "Autocomplete" && !String(df.options || "").trim()) return "text";
	return KINDS[df.fieldtype] || "text";
}

/** What a number filter is typed in, per stored unit: stars for a Rating. */
export function scale_of(df) {
	if (df.fieldtype === "Rating") return cint(df.options) || 5;
	return 1;
}

/** A Rating's stored share in stars, as its form shows them: whole or half. */
export function stars_of(df, value) {
	return Math.round(value * scale_of(df) * 2) / 2;
}

/** Stars as a Rating stores them: a share kept to 2 decimals like its column (3 of 7 is 0.43). */
export function rating_of(df, stars) {
	const most = scale_of(df);
	const picked = Math.round(Math.min(Math.max(stars, 0), most) * 2) / 2;
	return Math.round((picked / most) * 100) / 100;
}

/** A Link to a tree: a record there stands for its whole branch. */
export function is_tree(df) {
	return df.fieldtype === "Link" && frappe.boot.treeviews.includes(df.options);
}

/** Conditions an app adds through the `filters_config` hook (Fiscal Year) that fit this field. */
export function hook_conditions(df) {
	const config = frappe.boot.additional_filters_config || {};
	return Object.keys(config).filter((key) =>
		config[key].valid_for_fieldtypes?.includes(df.fieldtype)
	);
}

/** Whether a field can be empty: every record fills the standard ones, bar the lists in text. */
export function can_be_empty(df) {
	return df.match === "like" || frappe.model.is_non_std_field(df.fieldname);
}

export const strip_like = (value) => String(value).replace(/^%|%$/g, "");
export const is_blank = (value) => value === "" || value == null;

/** The values of an `in` filter, which comes as a list or as comma separated text. */
export function list_of(value) {
	if (Array.isArray(value)) return value;
	if (is_blank(value)) return [];
	return String(value)
		.split(",")
		.map((v) => v.trim())
		.filter(Boolean);
}

// a form's "Scan Barcode" box (Data, Barcode option) only fills in other fields; Advanced filters
// still reach it
export const is_scan_helper = (df) => df.fieldtype === "Data" && df.options === "Barcode";

/** A value as people read it: a record's title, a person's name, an option's translation. */
export function value_label(df, value) {
	if (is_blank(value)) return __("No value");
	if (Array.isArray(df.options)) {
		const option = df.options.find((o) => String(o.value ?? o) === String(value));
		if (option) return option.label ?? __(option);
	}
	if (df.fieldtype === "Select" || df.fieldtype === "Autocomplete")
		return __(value, null, df.doctype);
	if (df.fieldtype === "Link" && df.options === "User") {
		if (value === frappe.session.user) return __("Me");
		return frappe.utils.get_link_title("User", value) || frappe.user.full_name(value);
	}
	if (df.fieldtype === "Link") return frappe.utils.get_link_title(df.options, value) || value;
	return String(value);
}

// the desk shows no time as nothing; a filter's 0 reads as 0
export function duration_text(seconds) {
	return Number(seconds) ? frappe.utils.get_formatted_duration(seconds) : "0";
}

export const same_field = (a, b) =>
	a && b && a.doctype === b.doctype && a.fieldname === b.fieldname;

// a field every DocType has (owner, creation...); Document Status picks by name, not by number
export function std_field(doctype, fieldname) {
	if (fieldname === "docstatus") {
		return {
			fieldname,
			label: __("Document Status"),
			fieldtype: "Select",
			options: [
				{ value: 0, label: __("Draft") },
				{ value: 1, label: __("Submitted") },
				{ value: 2, label: __("Cancelled") },
			],
		};
	}
	const found = frappe.model.std_fields.find((d) => d.fieldname === fieldname);
	if (!found) return undefined;
	// every DocType has these, so each gets an icon of its own rather than its type's
	const df = { ...found, icon: STD_ICONS[fieldname] };
	if (LISTED_IN_TEXT[fieldname]) {
		const options = LISTED_IN_TEXT[fieldname];
		return { ...df, label: __(df.label), fieldtype: "Link", options, match: "like" };
	}
	return { ...df, label: __(df.label), options: fieldname === "name" ? doctype : df.options };
}

const STD_ICONS = {
	name: "hash",
	_assign: "user-check",
	owner: "user-plus",
	creation: "calendar-plus",
	modified_by: "user-pen",
	modified: "calendar-clock",
	_liked_by: "heart",
	_user_tags: "tag",
};

// Assigned To and Liked By keep users, Tags keeps tags, as a list in one text column
const LISTED_IN_TEXT = { _assign: "User", _liked_by: "User", _user_tags: "Tag" };
// fields every DocType has, in the order the desk's toolbar lists them
export const GROUP_BY_KEYS = { owner: "owner", assigned_to: "_assign", tags: "_user_tags" };
