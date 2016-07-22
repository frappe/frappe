// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.db = {
	get_value: function(doctype, filters, fieldname, callback) {
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: doctype,
				fieldname: fieldname,
				filters: filters
			},
			callback: function(r, rt) {
				callback(r.message);
			}
		});
	}
}
