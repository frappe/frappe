// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.db = {
	get_list: function(doctype, args) {
		if (!args) {
			args = {};
		}
		args.doctype = doctype;
		if (!args.fields) {
			args.fields = ['name'];
		}
		if (!args.limit) {
			args.limit = 20;
		}
		return new Promise ((resolve) => {
			frappe.call({
				method: 'frappe.model.db_query.get_list',
				args: args,
				callback: function(r) {
					resolve(r.message);
				}
			});
		});
	},
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
