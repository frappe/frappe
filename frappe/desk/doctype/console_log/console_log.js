// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Console Log", {
	refresh: function (frm) {
		frm.add_custom_button(__("Reload in Console"), () => {
			let system_console_doc = frappe.model.get_new_doc("System Console");
			system_console_doc["console"] = frm.doc.script;
			if (system_console_doc.doctype) {
				const sleep = frappe.utils.sleep;

				frappe.dom.freeze(__("Creating {0}", [system_console_doc.doctype]) + "...");
				// to avoid abrupt UX
				// wait for activity feedback
				sleep(500).then(() => {
					let res = frappe.model.with_doctype(system_console_doc.doctype, () => {
						frappe.set_route(
							"Form",
							system_console_doc.doctype,
							system_console_doc.name
						);
						frappe.dom.unfreeze();
					});
					res && res.fail(frappe.dom.unfreeze);
				});
			}
		});
	},
});
