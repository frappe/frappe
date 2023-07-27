// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Console Log", {
	refresh: function (frm) {
		frm.add_custom_button(__("Reload in Console"), () => {
			let system_console = frappe.model.get_new_doc("System Console");
			system_console.console = frm.doc.script;
			system_console.type = frm.doc.type;
			frappe.model.sync(system_console);
			frappe.set_route("Form", system_console.doctype, system_console.name);
		});
	},
});
