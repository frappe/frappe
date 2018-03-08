// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Route", {
	language: function(frm, cdt, cdn) {
		var d = frappe.model.get_doc(cdt, cdn);
		if (d.language && !d.route) {
			frappe.db.get_value('Translation', {language: d.language, source_name: frm.doc.route || frm.doc.title}, 'target_name', (r) => {
				if (r && r.target_name) {
					frappe.model.set_value(cdt, cdn, 'route', (d.language + '/'+ r.target_name));
				}
				else {
					frappe.model.set_value(cdt, cdn, 'route', (d.language + '/' + __(r.target_name)));
				}
			});
		}
	}
})