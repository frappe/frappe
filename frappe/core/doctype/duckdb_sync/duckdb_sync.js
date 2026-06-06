// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("DuckDB Sync", {
	sync_data: function (frm) {
		frm.call({
			doc: frm.doc,
			method: "sync_data",
		});
	},
});
