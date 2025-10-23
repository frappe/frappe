
// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bulk Customization Export", {
	refresh(frm) {
		frm.disable_save();
		set_custom_buttons(frm);

		if (!frappe.boot.developer_mode) {
			// make the document read-only
			frm.set_read_only();
			frm.dashboard.clear_comment();
			frm.dashboard.add_comment(
				__("You need to activate Developer Mode to use this tool."),
				"blue",
				true
			);
		} else if (frappe.boot.developer_mode) {
			frm.dashboard.clear_comment();
			let msg = __(
				"This site is running in developer mode. Any change made here will be updated in code."
			);
			frm.dashboard.add_comment(msg, "yellow", true);
		}
	},
});

function set_custom_buttons(frm) {
	if (frappe.boot.developer_mode) {
		frm.add_custom_button(__("Export Customizations"), function () {
			frappe.call({
				method: "frappe.custom.doctype.bulk_customization_export.bulk_customization_export.bulk_export_customizations",
				args: { doc: frm.doc },
				freeze: true,
				freeze_message: __("Exporting customizations..."),
				callback: function (r) {},
			});
		}).addClass("btn-primary");
	}
}
