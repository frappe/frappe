// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("DuckDB Dashboard", {
	force_sync: function (frm) {
		frm.call({
			method: "frappe.database.duckdb.database.sync_to_duckdb",
		});
	},
	connect: function (frm) {
		frm.call({
			method: "frappe.database.duckdb.database.open_duckdb_connection",
		});
	},
	close_connection: function (frm) {
		frm.call({
			method: "frappe.database.duckdb.database.close_connection",
		});
	},
	drop_all_tables: function (frm) {
		frm.call({
			method: "frappe.database.duckdb.database.drop_all_tables",
		});
	},
	drop_tables: function (frm) {
		frm.call({
			method: "frappe.database.duckdb.database.drop_tables",
		});
	},
});
