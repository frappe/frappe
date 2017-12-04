// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.db = {
	exists: function(doctype, name) {
		return new Promise ((resolve) => {
			frappe.db.get_value(doctype, {name: name}, 'name').then((r) => {
				(r.message && r.message.name) ? resolve(true) : resolve(false);
			});
		});
	},
	get_value: function(doctype, filters, fieldname, callback) {
		return frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: doctype,
				fieldname: fieldname,
				filters: filters
			},
			callback: function(r) {
				callback && callback(r.message);
			}
		});
	},
	set_value: function(doctype, docname, fieldname, value, callback) {
		return frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: doctype,
				name: docname,
				fieldname: fieldname,
				value: value
			},
			callback: function(r) {
				callback && callback(r.message);
			}
		});
	}
}
