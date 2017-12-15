// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Address", {
	refresh: function(frm) {
		if(frm.doc.__islocal) {
			var last_route = frappe.route_history.slice(-2, -1)[0];
			if(frappe.dynamic_link && frappe.dynamic_link.doc
					&& frappe.dynamic_link.doc.name==last_route[2]) {
				frm.add_child('links', {
					link_doctype: frappe.dynamic_link.doctype,
					link_name: frappe.dynamic_link.doc[frappe.dynamic_link.fieldname]
				});
			}
		}
		frm.set_query('link_doctype', "links", function() {
			return {
				query: "frappe.contacts.address_and_contact.filter_dynamic_link_doctypes",
				filters: {
					fieldtype: "HTML",
					fieldname: "address_html",
				}
			}
		});
		frm.refresh_field("links");
	},
	validate: function(frm) {
		// clear linked customer / supplier / sales partner on saving...
		if(frm.doc.links) {
			frm.doc.links.forEach(function(d) {
				frappe.model.remove_from_locals(d.link_doctype, d.link_name);
			});
		}
	},
	after_save: function() {
		frappe.run_serially([
			() => frappe.timeout(1),
			() => {
				var last_route = frappe.route_history.slice(-2, -1)[0];
				if(frappe.dynamic_link && frappe.dynamic_link.doc
					&& frappe.dynamic_link.doc.name == last_route[2]){
					frappe.set_route(last_route[0], last_route[1], last_route[2]);
				}
			}
		]);
	}
});
