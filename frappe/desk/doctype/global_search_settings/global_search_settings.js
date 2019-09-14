// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Global Search Settings', {
	refresh: function(frm) {
		frm.add_custom_button(__("Reset"), function () {
			frappe.call({
				method: "frappe.desk.doctype.global_search_settings.global_search_settings.reset_global_search_settings_doctypes",
				callback: function() {
					frappe.show_alert({
						message: __("Global Search Document Types Reset."),
						indicator: "green"
					});
					frm.refresh();
				}
			});
		});
	}
});
