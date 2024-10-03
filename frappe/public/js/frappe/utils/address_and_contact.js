frappe.provide("frappe.contacts");

$.extend(frappe.contacts, {
	clear_address_and_contact: function (frm) {
		$(frm.fields_dict["address_html"].wrapper).html("");
		frm.fields_dict["contact_html"] && $(frm.fields_dict["contact_html"].wrapper).html("");
	},

	render_address_and_contact: function (frm) {
		// render address
		if (frm.fields_dict["address_html"] && "addr_list" in frm.doc.__onload) {
			$(frm.fields_dict["address_html"].wrapper)
				.html(frappe.render_template("address_list", frm.doc.__onload))
				.find(".btn-address")
				.on("click", () => new_record("Address", frm));
		}

		// render contact
		if (frm.fields_dict["contact_html"] && "contact_list" in frm.doc.__onload) {
			$(frm.fields_dict["contact_html"].wrapper)
				.html(frappe.render_template("contact_list", frm.doc.__onload))
				.find(".btn-contact")
				.on("click", () => new_record("Contact", frm));
		}
	},
	get_last_doc: function (frm) {
		const reverse_routes = frappe.route_history.slice().reverse();
		const last_route = reverse_routes.find((route) => {
			return route[0] === "Form" && route[1] !== frm.doctype;
		});
		let doctype = last_route && last_route[1];
		let docname = last_route && last_route[2];

		if (last_route && last_route.length > 3) docname = last_route.slice(2).join("/");

		return {
			doctype,
			docname,
		};
	},
	get_address_display: function (frm, address_field, display_field) {
		if (frm.updating_party_details) {
			return;
		}

		let _address_field = address_field || "address";
		let _display_field = display_field || "address_display";

		if (!frm.doc[_address_field]) {
			frm.set_value(_display_field, "");
			return;
		}

		frappe
			.xcall("frappe.contacts.doctype.address.address.get_address_display", {
				address_dict: frm.doc[_address_field],
			})
			.then((address_display) => frm.set_value(_display_field, address_display));
	},
});

function new_record(doctype, frm) {
	frappe.dynamic_link = {
		doctype: frm.doc.doctype,
		doc: frm.doc,
		fieldname: "name",
	};

	if (frappe.boot.enable_address_autocompletion === 1 && doctype === "Address") {
		new frappe.ui.AddressAutocompleteDialog({
			title: __("New Address"),
			link_doctype: frm.doc.doctype,
			link_name: frm.doc.name,
			after_insert: function (doc) {
				frm.reload_doc();
			},
		}).show();
	} else {
		frappe.new_doc(doctype);
	}
}
