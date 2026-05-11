frappe.provide("frappe.contacts");

$.extend(frappe.contacts, {
	clear_address_and_contact: function (frm) {
		for (const field of ["address_html", "contact_html"]) {
			$(frm.fields_dict[field]?.wrapper)?.html("");
		}
	},

	render_address_and_contact: function (frm) {
		const items = [
			{
				field: "address_html",
				data: "addr_list",
				template: "address_list",
				btn: ".btn-address",
				doctype: "Address",
			},
			{
				field: "contact_html",
				data: "contact_list",
				template: "contact_list",
				btn: ".btn-contact",
				doctype: "Contact",
			},
		];

		for (const item of items) {
			// render address or contact
			const field_wrapper = frm.fields_dict[item.field]?.wrapper;

			if (field_wrapper && frm.doc.__onload && item.data in frm.doc.__onload) {
				$(field_wrapper)
					.html(frappe.render_template(item.template, frm.doc.__onload))
					.find(item.btn)
					.on("click", () => new_record(item.doctype, frm.doc));
			}
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

function new_record(doctype, source_doc) {
	frappe.dynamic_link = {
		doctype: source_doc.doctype,
		doc: source_doc,
		fieldname: "name",
	};

	return frappe.new_doc(doctype);
}
