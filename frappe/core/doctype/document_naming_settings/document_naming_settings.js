// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Document Naming Settings", {
	onload: function(frm) {
		frm.events.get_doc_and_prefix(frm);
	},

	refresh: function(frm) {
		frm.disable_save();
	},

	get_doc_and_prefix: function(frm) {
		frappe.call({
			method: "get_transactions",
			doc: frm.doc,
			callback: function(r) {
				frm.set_df_property(
					"transaction_type",
					"options",
					r.message.transactions
				);
				frm.set_df_property("prefix", "options", r.message.prefixes);
			},
		});
	},

	transaction_type: function(frm) {
		frm.set_value("user_must_always_select", 0);
		frappe.call({
			method: "get_options",
			doc: frm.doc,
			callback: function(r) {
				frm.set_value("naming_series_options", r.message);
				if (r.message && r.message.split("\n")[0] == "")
					frm.set_value("user_must_always_select", 1);
			},
		});
	},

	prefix: function(frm) {
		frappe.call({
			method: "get_current",
			doc: frm.doc,
			callback: function(r) {
				frm.refresh_field("current_value");
			},
		});
	},

	update: function(frm) {
		frappe.call({
			method: "update_series",
			doc: frm.doc,
			callback: function(r) {
				frm.events.get_doc_and_prefix(frm);
			},
		});
	},

	try_naming_series(frm) {
		frappe.call({
			method: "preview_series",
			doc: frm.doc,
			callback: function(r) {
				if (!r.exc) {
					frm.set_value("preview", r.message);
				} else {
					frm.set_value(
						"preview",
						__("Failed to generate preview of series")
					);
				}
			},
		});
	},
});
