// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("DuckDB Sync", {
	refresh: function (frm) {
		frm.set_query("doc_type", function () {
			return {
				filters: {
					istable: 0,
					issingle: 0,
					is_virtual: 0,
				},
			};
		});
	},
	sync_data: function (frm) {
		frm.call({
			doc: frm.doc,
			method: "sync_data",
		});
	},
});
