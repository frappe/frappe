// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Address", {
	refresh: function(frm) {
		if(frm.doc.__islocal) {
			var last_route = frappe.route_history.slice(-2, -1)[0];
			if(frappe.contact_link && frappe.contact_link.doc
					&& frappe.contact_link.doc.name==last_route[2]) {
				frm.add_child('links', {
					link_doctype: frappe.contact_link.doctype,
					link_name: frappe.contact_link.doc[frappe.contact_link.fieldname]
				});
			}
		}
	},
	validate: function(frm) {
		// clear linked customer / supplier / sales partner on saving...
		if(frm.doc.links) {
			frm.doc.links.forEach(function(d) {
				frappe.model.remove_from_locals(d.link_doctype, d.link_name);
			});
		}
	}
});
