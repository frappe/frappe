// Human-readable descriptions of a Link field's applied filters, one per
// filter, as plain text (for example "Customer Group equals \"Commercial\"").
// Used by the combobox Link field for its filter chips. Mirrors the describer inside the classic
// ControlLink (kept separate so that file stays untouched).

export async function describe_link_filters(doctype, filters) {
	let filter_array = [];

	// convert object style to array
	if (!Array.isArray(filters)) {
		for (let fieldname in filters) {
			let value = filters[fieldname];
			if (!Array.isArray(value)) {
				value = ["=", value];
			}
			filter_array.push([doctype, fieldname, ...value]); // [doctype, fieldname, operator, value]
		}
	} else {
		filter_array = filters.slice(); // clone
	}

	// add doctype if missing: [doctype, fieldname, operator, value]
	filter_array = filter_array.map((f) => (f.length === 3 ? [doctype, ...f] : f));

	function formatValueForDisplay(docfield, val) {
		// Check boolean fields -> show Yes/No (localized)
		// Handles 0/1, true/false values
		if (docfield && docfield.fieldtype === "Check") {
			return val == 1 || val === true ? __("Yes") : __("No");
		}

		// Array values -> truncate to first 5, append "..."
		if (Array.isArray(val)) {
			const filtered = val.filter((v) => v != null && v !== "");
			const arr = filtered.slice(0, 5).map((v) => {
				// Strings in quotes, numbers/dates not quoted
				if (typeof v === "string") {
					return `"${String(__(v))}"`;
				}
				// Numbers, dates, etc. - not translated, not quoted
				return String(v);
			});
			if (filtered.length > 5) arr.push("...");
			return arr.join(", ");
		}

		// Null / empty
		if (val == null || val === "") {
			return __("empty", null, "Comparison value is empty");
		}

		// Format based on type: strings in quotes, numbers/dates not quoted
		if (typeof val === "string") {
			return `"${String(__(val))}"`;
		}

		// Numbers, dates, etc. - not translated, not quoted
		return frappe.format(val, docfield || {}, { inline: true });
	}

	async function describe_filter(filter) {
		// expect [doctype, fieldname, operator, value]
		const _doctype = filter[0];
		const fieldname = filter[1];
		const operator = filter[2];
		let value = filter[3];

		const docfield = frappe.meta.get_docfield(_doctype, fieldname);
		const label = docfield ? docfield.label : frappe.model.unscrub(fieldname);
		const fieldtype = docfield ? docfield.fieldtype : null;

		const labelDisplay = String(__(label, null, _doctype));
		const valueDisplay = formatValueForDisplay(docfield, value);
		const is_time_like = ["Date", "Datetime", "Time"].includes(fieldtype);

		// Handle all operators with translation and interpolation in one call
		switch (operator) {
			case "=":
				if (fieldtype === "Check") {
					if (fieldname === "enabled") {
						return value == 1
							? __("is enabled") // ["enabled", "=", 1]
							: __("is disabled"); // ["enabled", "=", 0]
					}

					if (fieldname === "disabled") {
						return value == 1
							? __("is disabled") // ["disabled", "=", 1]
							: __("is enabled"); // ["disabled", "=", 0]
					}

					return value == 1
						? __("{0} is enabled", [labelDisplay])
						: __("{0} is disabled", [labelDisplay]);
				}
				return __("{0} equals {1}", [labelDisplay, valueDisplay]);
			case "!=":
				if (fieldtype === "Check") {
					if (fieldname === "enabled") {
						return value == 1
							? __("is disabled") // ["enabled", "!=", 1]
							: __("is enabled"); // ["enabled", "!=", 0]
					}

					if (fieldname === "disabled") {
						return value == 1
							? __("is enabled") // ["disabled", "!=", 1]
							: __("is disabled"); // ["disabled", "!=", 0]
					}

					return value == 1
						? __("{0} is disabled", [labelDisplay])
						: __("{0} is enabled", [labelDisplay]);
				}
				return __("{0} is not equal to {1}", [labelDisplay, valueDisplay]);
			case "in":
				return __("{0} is one of {1}", [labelDisplay, valueDisplay]);
			case "not in":
				return __("{0} is not one of {1}", [labelDisplay, valueDisplay]);
			case "like":
				return __("{0} contains {1}", [labelDisplay, valueDisplay]);
			case "not like":
				return __("{0} does not contain {1}", [labelDisplay, valueDisplay]);
			case ">":
				if (is_time_like) {
					return __("{0} is after {1}", [labelDisplay, valueDisplay]);
				}
				return __("{0} is greater than {1}", [labelDisplay, valueDisplay]);
			case "<":
				if (is_time_like) {
					return __("{0} is before {1}", [labelDisplay, valueDisplay]);
				}
				return __("{0} is less than {1}", [labelDisplay, valueDisplay]);
			case ">=":
				if (is_time_like) {
					return __("{0} is on or after {1}", [labelDisplay, valueDisplay]);
				}
				return __("{0} is greater than or equal to {1}", [labelDisplay, valueDisplay]);
			case "<=":
				if (is_time_like) {
					return __("{0} is on or before {1}", [labelDisplay, valueDisplay]);
				}
				return __("{0} is less than or equal to {1}", [labelDisplay, valueDisplay]);
			case "is":
				if (value == "set") {
					return __("{0} is set", [labelDisplay]);
				}
				if (value == "not set") {
					return __("{0} is not set", [labelDisplay]);
				}
				return __("{0} is {1}", [labelDisplay, valueDisplay]);
			case "between":
				if (Array.isArray(value) && value.length === 2) {
					return __("{0} is between {1} and {2}", [
						labelDisplay,
						formatValueForDisplay(docfield, value[0]),
						formatValueForDisplay(docfield, value[1]),
					]);
				}
				return __("{0} is between {1}", [labelDisplay, valueDisplay]);
			case "descendants of":
				return __("{0} is a descendant of {1}", [labelDisplay, valueDisplay]);
			case "ancestors of":
				return __("{0} is an ancestor of {1}", [labelDisplay, valueDisplay]);
			case "not descendants of":
				return __("{0} is not a descendant of {1}", [labelDisplay, valueDisplay]);
			case "not ancestors of":
				return __("{0} is not an ancestor of {1}", [labelDisplay, valueDisplay]);
			case "timespan":
				return __("{0} is within {1}", [labelDisplay, valueDisplay]);
			default:
				// Fallback for unknown operators (no translatable text here)
				return [labelDisplay, operator, valueDisplay].join(" ");
		}
	}

	// load each doctype's meta once, not once per filter
	for (const dt of new Set(filter_array.map((f) => f[0]))) {
		await frappe.model.with_doctype(dt, () => {});
	}
	return Promise.all(filter_array.map((filter) => describe_filter(filter)));
}
