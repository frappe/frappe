// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Address", {
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
		// Check when save an address if the email, phone number or fax is already registered in another address,
		// and shows a popup to the user with links to the address
		frappe.call({
			method: 'frappe.contacts.address_and_contact.check_address_email_phone_fax_already_exist',
			args: {
				email_id: frm.doc.email_id,
				phone: frm.doc.phone,
				fax: frm.doc.fax,
				name: frm.doc.name
			},
			callback: function (r) {
				if (r.message) {
					
					var variant = r.message;
					var values = "";						
					var addresses = variant.split(",");
					
					for (var i=0; i < addresses.length; i++) {
						var address_field = addresses[i].split(";"); // position [1]
						var address = address_field[0].split(":");
						
						var link = repl('<a target="_blank" href="#Form/' + address_field[1] + '/%(name)s"' +
								'class="strong variant-click">%(label)s</a>', {
							name: encodeURIComponent(address[1]),
							label: address[1]
						});
						
						var address_label = address[0].split("/");
						
						if (address_label[0] == "Email ID")
							values += "* Email ID " + frm.doc.email_id + " is already in use on " + address_field[1] +
									": " + link + " as an " + address_label[1] + "<br>";
						else if (address_label[0] == "Phone")
							values += "* Phone " + frm.doc.phone + " is already in use on " + address_field[1] +
									": "+ link + " as a " + address_label[1] + "<br>";
						else
							values += "* Fax " + frm.doc.fax + " is already in use on " + address_field[1] +
									": " + link + " as a " + address_label[1] + "<br>";
					}
											
					frappe.show_alert(values, 300);
				}
			}
		});
	}
});
