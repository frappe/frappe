frappe.provide("frappe.utils.datatable");

frappe.utils.datatable.get_translations = function () {
	let translations = {};
	translations[frappe.boot.lang] = {
		"Sort Ascending": __("Sort Ascending"),
		"Sort Descending": __("Sort Descending"),
		"Reset sorting": __("Reset sorting"),
		"Remove column": __("Remove column"),
		"No Data": __("No Data"),
		"{count} cells copied": {
			"1": __("{count} cell copied"),
			"default": __("{count} cells copied")
		},
		"{count} rows selected": {
			"1": __("{count} row selected"),
			"default": __("{count} rows selected")
		}
	};

	return translations;
};
