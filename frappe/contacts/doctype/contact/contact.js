// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt


cur_frm.email_field = "email_id";
frappe.ui.form.on("Contact", {
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

		if(!frm.doc.user && !frm.is_new() && frm.perm[0].write) {
			frm.add_custom_button(__("Invite as User"), function() {
				return frappe.call({
					method: "frappe.contacts.doctype.contact.contact.invite_user",
					args: {
						contact: frm.doc.name
					},
					callback: function(r) {
						frm.set_value("user", r.message);
					}
				});
			});
		}
		frm.set_query('link_doctype', "links", function() {
			return {
				query: "frappe.contacts.address_and_contact.filter_dynamic_link_doctypes",
				filters: {
					fieldtype: "HTML",
					fieldname: "contact_html",
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
	}
});

frappe.ui.form.on("Dynamic Link", {
	link_name:function(frm, cdt, cdn){
		var child = locals[cdt][cdn];
		if(child.link_name) {
			frappe.model.with_doctype(child.link_doctype, function () {
				var title_field = frappe.get_meta(child.link_doctype).title_field || "name"
				frappe.model.get_value(child.link_doctype, child.link_name, title_field, function (r) {
					frappe.model.set_value(cdt, cdn, "link_title", r[title_field])
				})
			})
		}
	}
})
