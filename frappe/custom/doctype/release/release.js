// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Release', {
	refresh: function(frm) {
		frm.add_custom_button(__("Go to Package"), function() {
			frappe.set_route("Form", "Package", "Package");
		});

		frm.add_custom_button(__("Release"), function() {
			frm.call("create_release").then(() => {});
		});

		frappe.realtime.on("exporting_package", (data) => {
			if (data.progress !== (data.total-1)) {
				frm.dashboard.show_progress("Releasing Package", data.progress / data.total * 100, __("{0}", [data.message]));
			} else {
				frm.dashboard.hide_progress();
			}
		});
	}
});
