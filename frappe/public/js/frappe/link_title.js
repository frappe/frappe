// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for link titles
frappe._link_titles = {};

frappe.get_link_title = function(doctype, name) {
	if (!doctype || !name) {
		return;
	}

	return frappe._link_titles[doctype + "::" + name];
}

frappe.add_link_title = function (doctype, name, value) {
	if (!doctype || !name) {
		return;
	}

	frappe._link_titles[doctype + "::" + name] = value;
}
