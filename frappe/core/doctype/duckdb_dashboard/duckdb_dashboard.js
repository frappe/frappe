// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("DuckDB Dashboard", {
	refresh(frm) {
		frm.add_custom_button(__("Force Sync"), () => {
			frm.call({
				method: "frappe.database.duckdb.database.sync_to_duckdb",
			});
		});
		frm.add_custom_button(__("Drop all tables"), () => {
			frm.call({
				method: "frappe.database.duckdb.database.drop_all_tables",
			});
		});
	},
});
