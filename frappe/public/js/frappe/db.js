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
	get_value: function(doctype, filters, fieldname, callback, parent) {
		return frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: doctype,
				fieldname: fieldname,
				filters: filters,
				parent: parent
			},
			callback: function(r) {
				callback && callback(r.message);
			}
		});
	},
	get_single_value: (doctype, field) => {
		return new Promise(resolve => {
			frappe.call('frappe.client.get_single_value', { doctype, field })
				.then(r => resolve(r ? r.message : null));
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
	},
	get_doc: function(doctype, name, filters = null) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "frappe.client.get",
				args: { doctype, name, filters },
				callback: r => resolve(r.message)
			}).fail(reject);
		});
	},
	insert: function(doc) {
		return new Promise(resolve => {
			frappe.call('frappe.client.insert', { doc }, r => resolve(r.message));
		});
	},
	delete_doc: function(doctype, name) {
		return new Promise(resolve => {
			frappe.call('frappe.client.delete', { doctype, name }, r => resolve(r.message));
		});
	},
	count: function(doctype, args={}) {
		return new Promise(resolve => {
			frappe.call(
				'frappe.client.get_count',
				Object.assign(args, { doctype }),
				r => resolve(r.message)
			);
		});
	}
};
