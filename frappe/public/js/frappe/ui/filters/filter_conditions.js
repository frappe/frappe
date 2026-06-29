// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
// License: MIT. See LICENSE

/**
 * Shared filter operator / condition definitions.
 *
 * Single source of truth for both the legacy jQuery filter UI (`frappe.ui.Filter`)
 * and the Vue advanced-filter UI. Keeping the operator list, the per-fieldtype
 * validity map, and the value-control mapping in one module guarantees the two
 * UIs can never drift in which operators exist or how a value input is rendered.
 *
 * Everything here is also exposed on `frappe.ui.filter_conditions` and
 * `frappe.ui.filter_utils` for runtime consumers (including other apps).
 */

/** Base operators plus the nested-set operators, as `[operator, label]` pairs. */
export function get_conditions() {
	const conditions = [
		["=", __("Equals")],
		["!=", __("Not Equals")],
		["like", __("Like")],
		["not like", __("Not Like")],
		["in", __("In")],
		["not in", __("Not In")],
		["is", __("Is")],
		[">", __("Greater Than")],
		["<", __("Less Than")],
		[">=", __("Greater Than Or Equal To")],
		["<=", __("Less Than Or Equal To")],
		["Between", __("Between")],
		["Timespan", __("Timespan")],
	];

	conditions.push(...get_nested_set_conditions());
	return conditions;
}

/** Operators only valid for Link fields that point to a nested-set doctype. */
export function get_nested_set_conditions() {
	return [
		["descendants of", __("Descendants Of")],
		["descendants of (inclusive)", __("Descendants Of (inclusive)")],
		["not descendants of", __("Not Descendants Of")],
		["ancestors of", __("Ancestors Of")],
		["not ancestors of", __("Not Ancestors Of")],
	];
}

/** Context-specific operator labels for Date / Datetime fields (e.g. "<" -> "Before"). */
export function get_special_condition_labels() {
	return {
		Date: {
			"<": __("Before"),
			">": __("After"),
			"<=": __("On or Before"),
			">=": __("On or After"),
		},
		Datetime: {
			"<": __("Before"),
			">": __("After"),
			"<=": __("On or Before"),
			">=": __("On or After"),
		},
	};
}

/** Map of fieldtype -> operators that are NOT valid for that fieldtype. */
export function build_invalid_condition_map(conditions = get_conditions()) {
	const range_conditions = ["Between", "Timespan"];
	const comparison_conditions = [">", "<", ">=", "<="];
	const like_conditions = ["like", "not like"];
	const in_conditions = ["in", "not in"];
	const equality_conditions = ["=", "!="];

	const text_fields = [
		"Code",
		"HTML Editor",
		"Markdown Editor",
		"Text Editor",
		"Small Text",
		"Long Text",
		"Text",
		"Password",
	];

	const numeric_fields = ["Rating", "Int", "Float", "Percent"];

	const text_invalid_conditions = [...range_conditions, ...comparison_conditions, ...in_conditions];

	const numeric_invalid_conditions = [...like_conditions, ...range_conditions, ...in_conditions];

	return {
		Date: like_conditions,
		Time: range_conditions,
		Data: range_conditions,
		Currency: range_conditions,

		Link: [...range_conditions, ...comparison_conditions],
		Color: [...range_conditions, ...comparison_conditions],

		Datetime: [...like_conditions, ...in_conditions, ...equality_conditions],
		Select: [...like_conditions, ...range_conditions, ...comparison_conditions],

		Check: conditions.map(([condition]) => condition).filter((condition) => condition !== "="),

		...Object.fromEntries(text_fields.map((field) => [field, [...text_invalid_conditions]])),

		...Object.fromEntries(numeric_fields.map((field) => [field, [...numeric_invalid_conditions]])),
	};
}

/**
 * Merge pluggable operators contributed by apps via `additional_filters_config`
 * into the conditions list and the invalid-condition map (mutates both in place).
 */
export function apply_additional_filters_config(conditions, invalid_condition_map) {
	const filters_config = frappe.boot.additional_filters_config;
	if (!filters_config) return { conditions, invalid_condition_map };

	for (let key of Object.keys(filters_config)) {
		const filter = filters_config[key];
		conditions.push([key, __(filter.label)]);
		for (let fieldtype of Object.keys(invalid_condition_map)) {
			if (!filter.valid_for_fieldtypes.includes(fieldtype)) {
				invalid_condition_map[fieldtype].push(key);
			}
		}
	}

	return { conditions, invalid_condition_map };
}

/** Whether nested-set operators should be offered for the given field. */
export function is_nested_set_field(df) {
	return df.fieldtype === "Link" && (frappe.boot.nested_set_doctypes || []).includes(df.options);
}

/**
 * Fieldtype override implied by the chosen operator, mirroring the legacy filter
 * UI: `in`/`like`/`not in`/`not like` fall back to plain Data, while a Select /
 * MultiSelect field with `in`/`not in` keeps a native MultiSelect control.
 */
export function get_fieldtype_override(df, condition) {
	let fieldtype = null;
	if (["in", "like", "not in", "not like"].includes(condition)) {
		fieldtype = "Data";
	}
	if (["Select", "MultiSelect"].includes(df.fieldtype) && ["in", "not in"].includes(condition)) {
		fieldtype = "MultiSelect";
	}
	return fieldtype;
}

/**
 * Operators valid for a given field, as `[operator, label]` pairs ready for an
 * operator dropdown. Invalid operators are filtered out (keyed on the field's
 * original type), nested-set operators appear only for nested-set link fields,
 * and Date/Datetime comparison operators get their context-specific labels.
 */
export function get_valid_conditions_for_field(df, cache) {
	let conditions, invalid_condition_map;
	if (cache) {
		({ conditions, invalid_condition_map } = cache);
	} else {
		conditions = get_conditions();
		invalid_condition_map = build_invalid_condition_map(conditions);
		apply_additional_filters_config(conditions, invalid_condition_map);
	}

	const original_type = df.original_type || df.fieldtype;
	const invalid = invalid_condition_map[original_type] || invalid_condition_map[df.fieldtype] || [];
	const nested_operators = get_nested_set_conditions().map(([operator]) => operator);
	const show_nested = is_nested_set_field(df);
	const special_labels = get_special_condition_labels()[original_type] || {};

	return conditions
		.filter(([operator]) => !invalid.includes(operator))
		.filter(([operator]) => (nested_operators.includes(operator) ? show_nested : true))
		.map(([operator, label]) => [operator, special_labels[operator] || label]);
}

/**
 * Value-control helpers, shared verbatim with the legacy filter UI. Kept as a
 * single object so `set_fieldtype` can call `this.get_timespan_options`.
 */
export const filter_utils = {
	get_formatted_value(field, value) {
		if (field.df.fieldname === "docstatus") {
			value = { 0: "Draft", 1: "Submitted", 2: "Cancelled" }[value] || value;
		} else if (field.df.original_type === "Check") {
			value = { 0: "No", 1: "Yes" }[cint(value)];
		}
		return frappe.format(value, field.df, { only_value: 1 });
	},

	get_selected_value(field, condition) {
		if (!field) return;

		let val = field.get_value() ?? field.value;

		if (!val && ["Link", "Dynamic Link"].includes(field.df.fieldtype)) {
			// HACK: link field with show title are async so their input value is "" but they have
			// some actual value set.
			val = field.value;
		}

		if (typeof val === "string") {
			val = strip(val);
		}

		if (condition == "is" && !val) {
			val = field.df.options[0].value;
		}

		if (field.df.original_type == "Check") {
			val = val == "Yes" ? 1 : 0;
		}

		if (["like", "not like"].includes(condition)) {
			// automatically append wildcards
			if (val && !(val.startsWith("%") || val.endsWith("%"))) {
				val = "%" + val + "%";
			}
		} else if (["in", "not in"].includes(condition)) {
			if (val) {
				try {
					const parsed = JSON.parse(val);
					val = Array.isArray(parsed) ? parsed : [String(parsed)];
				} catch {
					val = val
						.split(",")
						.map((v) => strip(v))
						.filter((v) => v != null && v !== "");
				}
			}
		} else if (frappe.boot.additional_filters_config[condition]) {
			val = field.value || val;
		}
		if (val === "%") {
			val = "";
		}

		return val;
	},

	get_selected_label(field) {
		if (["Link", "Dynamic Link"].includes(field.df.fieldtype)) {
			return field.get_label_value();
		}
	},

	get_default_condition(df) {
		const meta = frappe.get_meta(df.parent);
		if (df.fieldtype == "Data" && !meta?.is_large_table) {
			return "like";
		} else if (df.fieldtype == "Date" || df.fieldtype == "Datetime") {
			return "Between";
		} else {
			return "=";
		}
	},

	prepare_filter_docfield(original_docfield) {
		// A filter's value control must never be read-only, hidden, or gated by a
		// depends_on. Returns a fresh copy so the source docfield is untouched.
		const df = copy_dict(original_docfield);
		df.read_only = 0;
		df.hidden = 0;
		df.is_filter = true;
		delete df.hidden_due_to_dependency;
		return df;
	},

	set_fieldtype(df, fieldtype, condition) {
		// reset
		if (df.original_type) df.fieldtype = df.original_type;
		else df.original_type = df.fieldtype;

		df.description = "";
		df.reqd = 0;
		df.length = 1000; // this won't be saved, no need to apply 140 character limit here
		df.ignore_link_validation = true;

		// given
		if (fieldtype) {
			df.fieldtype = fieldtype;
			return;
		}

		// scrub
		if (df.fieldname == "docstatus") {
			df.fieldtype = "Select";
			df.options = [
				{ value: 0, label: __("Draft") },
				{ value: 1, label: __("Submitted") },
				{ value: 2, label: __("Cancelled") },
			];
		} else if (df.fieldtype == "Check") {
			df.fieldtype = "Select";
			df.options = [
				{ label: __("Yes", null, "Checkbox is checked"), value: "Yes" },
				{ label: __("No", null, "Checkbox is not checked"), value: "No" },
			];
		} else if (
			[
				"Text",
				"Small Text",
				"Text Editor",
				"Code",
				"Attach",
				"Attach Image",
				"Markdown Editor",
				"HTML Editor",
				"Tag",
				"Phone",
				"JSON",
				"Comments",
				"Barcode",
				"Dynamic Link",
				"Read Only",
				"Assign",
				"Color",
			].indexOf(df.fieldtype) != -1
		) {
			df.fieldtype = "Data";
		} else if (
			df.fieldtype == "Link" &&
			[
				"=",
				"!=",
				"descendants of",
				"descendants of (inclusive)",
				"ancestors of",
				"not descendants of",
				"not ancestors of",
			].indexOf(condition) == -1
		) {
			df.fieldtype = "Data";
		}
		if (df.fieldtype === "Data" && (df.options || "").toLowerCase() === "email") {
			df.options = null;
		}
		if (condition == "Between" && (df.fieldtype == "Date" || df.fieldtype == "Datetime")) {
			df.fieldtype = "DateRange";
		}
		if (
			condition == "Timespan" &&
			["Date", "Datetime", "DateRange", "Select"].includes(df.fieldtype)
		) {
			df.fieldtype = "Select";
			df.options = this.get_timespan_options([
				"Last",
				"Yesterday",
				"Today",
				"Tomorrow",
				"This",
				"Next",
			]);
		}
		if (condition === "is") {
			df.fieldtype = "Select";
			df.options = [
				{ label: __("Set", null, "Field value is set"), value: "set" },
				{ label: __("Not Set", null, "Field value is not set"), value: "not set" },
			];
		}
		return;
	},

	/**
	 * Generates timespan options for filter dropdown based on provided periods
	 * @param {Array<string>} periods - Array of period types to include
	 *     (e.g., "Last", "This", "Next", "Yesterday", "Today", "Tomorrow").
	 *     Additional custom values are allowed. The order of the periods is preserved.
	 * @returns {Array<{label: string, value: string}>} Array of option objects with label and value properties for the filter dropdown
	 */
	get_timespan_options(periods) {
		const last_options = [
			{ label: __("Last 7 Days"), value: "last 7 days" },
			{ label: __("Last 14 Days"), value: "last 14 days" },
			{ label: __("Last 30 Days"), value: "last 30 days" },
			{ label: __("Last 90 Days"), value: "last 90 days" },
			{ label: __("Last Week"), value: "last week" },
			{ label: __("Last Month"), value: "last month" },
			{ label: __("Last Quarter"), value: "last quarter" },
			{ label: __("Last 6 Months"), value: "last 6 months" },
			{ label: __("Last Year"), value: "last year" },
		];
		const this_options = [
			{ label: __("This Week"), value: "this week" },
			{ label: __("This Month"), value: "this month" },
			{ label: __("This Quarter"), value: "this quarter" },
			{ label: __("This Year"), value: "this year" },
		];
		const next_options = [
			{ label: __("Next 7 Days"), value: "next 7 days" },
			{ label: __("Next 14 Days"), value: "next 14 days" },
			{ label: __("Next 30 Days"), value: "next 30 days" },
			{ label: __("Next Week"), value: "next week" },
			{ label: __("Next Month"), value: "next month" },
			{ label: __("Next Quarter"), value: "next quarter" },
			{ label: __("Next 6 Months"), value: "next 6 months" },
			{ label: __("Next Year"), value: "next year" },
		];

		const options = [];
		for (const period of periods) {
			switch (period) {
				case "Last":
					options.push(...last_options);
					break;
				case "This":
					options.push(...this_options);
					break;
				case "Next":
					options.push(...next_options);
					break;
				case "Yesterday":
					options.push({ label: __("Yesterday"), value: "yesterday" });
					break;
				case "Today":
					options.push({ label: __("Today"), value: "today" });
					break;
				case "Tomorrow":
					options.push({ label: __("Tomorrow"), value: "tomorrow" });
					break;
				default:
					options.push({ label: __(period), value: `${period.toLowerCase()}` });
					break;
			}
		}

		return options;
	},
};

// Expose on the global namespace for runtime consumers (including other apps).
frappe.provide("frappe.ui");
frappe.ui.filter_utils = filter_utils;
frappe.ui.filter_conditions = {
	get_conditions,
	get_nested_set_conditions,
	get_special_condition_labels,
	build_invalid_condition_map,
	apply_additional_filters_config,
	is_nested_set_field,
	get_fieldtype_override,
	get_valid_conditions_for_field,
	filter_utils,
};
