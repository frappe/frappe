// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

cur_frm.email_field = "email_id";
frappe.ui.form.on("Contact", {
	refresh: function(frm) {
		if(frm.doc.__islocal) {
			const last_doc = frappe.contacts.get_last_doc(frm);
			if(frappe.dynamic_link && frappe.dynamic_link.doc
					&& frappe.dynamic_link.doc.name == last_doc.docname) {
				frm.set_value('links', '');
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
	},
	after_save: function(frm) {
		frappe.run_serially([
			() => frappe.timeout(1),
			() => {
				const last_doc = frappe.contacts.get_last_doc(frm);
				if(frappe.dynamic_link && frappe.dynamic_link.doc
					&& frappe.dynamic_link.doc.name == last_doc.docname){
					frappe.set_route('Form', last_doc.doctype, last_doc.docname);
				}
			}
		]);
		// Check when save a contact if the email, phone number or mobile number is already registered in another contact,
		// and shows a popup to the user with links to the contact
		frappe.call({
			method: 'frappe.contacts.address_and_contact.check_contact_email_phone_mobile_number_already_exist',
			args: {
				email_id: frm.doc.email_id,
				phone: frm.doc.phone,
				mobile_no: frm.doc.mobile_no,
				name: frm.doc.name
			},
			callback: function (r) {
				if (r.message) {
					
					var variant = r.message;
					var values = "";						
					var contacts = variant.split(",");
					
					for (var i=0; i < contacts.length; i++) {
						var contact_field = contacts[i].split(";"); // position [1]
						var contact = contact_field[0].split(":");
						
						var link = repl('<a target="_blank" href="#Form/' + contact_field[1] + '/%(name)s"' +
								'class="strong variant-click">%(label)s</a>', {
							name: encodeURIComponent(contact[1]),
							label: contact[1]
						});
						
						var contact_label = contact[0].split("/");
						
						if (contact_label[0] == "Email ID")
							values += "* Email ID " + frm.doc.email_id + " is already in use on " + contact_field[1] +
									": " + link + " as an " + contact_label[1] + "<br>";
						else if (contact_label[0] == "Phone")
							values += "* Phone " + frm.doc.phone + " is already in use on " + contact_field[1] +
									": " + link + " as a " + contact_label[1] + "<br>";
						else
							values += "* Mobile Number " + frm.doc.mobile_no + " is already in use on " + contact_field[1] +
									": " + link + " as a " + contact_label[1] + "<br>";
					}
											
					frappe.show_alert(values, 300);
				}
			}
		});
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
