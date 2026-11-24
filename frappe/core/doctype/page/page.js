// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Page", {
	setup: function (frm) {
		const prefix = "frappe.studio.";
		frm.set_query("studio_app", () => ({
			filters: {
				name: [
					"in",
					(frappe.boot.ui_islands || [])
						.filter((island) => island.startsWith(prefix))
						.map((island) => island.slice(prefix.length)),
				],
			},
		}));
	},
	refresh: function (frm) {
		const is_island_reference =
			frm.doc.standard === "No" && ["Frappe UI", "Studio App"].includes(frm.doc.type);
		if (
			!frappe.boot.developer_mode &&
			frappe.session.user != "Administrator" &&
			!frm.is_new() &&
			!is_island_reference
		) {
			frm.set_read_only();
		}
		if (frm.is_new() && !frappe.boot.developer_mode) {
			frm.set_value("standard", "No");
			frm.set_df_property("standard", "read_only", 1);
		}
		if (!frm.is_new() && !frm.doc.istable) {
			frm.add_custom_button(__("Go to {0} Page", [frm.doc.title || frm.doc.name]), () => {
				frappe.set_route(frm.doc.name);
			});
		}
	},
});
