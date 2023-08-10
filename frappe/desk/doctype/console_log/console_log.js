// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Console Log", {
	refresh: function (frm) {
		frm.add_custom_button(__("Re-Run in Console"), () => {
			localStorage.setItem("system_console_code", frm.doc.script);
			localStorage.setItem("system_console_type", frm.doc.type);
			frappe.set_route("Form", "System Console");
		});
	},
});
