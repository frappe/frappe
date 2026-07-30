frappe.provide("frappe.contacts");

$.extend(frappe.contacts, {
	clear_address_and_contact: function (frm) {
		for (const field of ["address_html", "contact_html"]) {
			$(frm.fields_dict[field]?.wrapper)?.html("");
		}
	},

	render_address_and_contact: function (frm) {
		const sections = [
			{
				doctype: "Address",
				field: "address_html",
				data: "addr_list",
				template: "address_list",
				btn: ".btn-address",
				primary_flag: "is_primary_address",
			},
			{
				doctype: "Contact",
				field: "contact_html",
				data: "contact_list",
				template: "contact_list",
				btn: ".btn-contact",
				primary_flag: "is_primary_contact",
			},
		];

		for (const section of sections) {
			const field_wrapper = frm.fields_dict[section.field]?.wrapper;
			if (!field_wrapper || !frm.doc.__onload || !(section.data in frm.doc.__onload)) continue;

			const records = frm.doc.__onload[section.data] || [];
			const primary_name = get_primary_name(frm, section, records);

			const $wrapper = $(field_wrapper).html(
				frappe.render_template(section.template, { ...frm.doc.__onload, primary_name })
			);
			$wrapper.find(section.btn).on("click", () => new_record(section.doctype, frm));
			const by_name = Object.fromEntries(records.map((r) => [r.name, r]));
			$wrapper.find(".card-menu-btn").each(function () {
				const record = by_name[this.closest("[data-name]")?.dataset.name];
				if (!record) return;
				new frappe.ui.Dropdown({
					trigger: this,
					options: card_menu(frm, section, record, primary_name),
					align: "end",
				});
			});
		}
	},

	get_last_doc: function (frm) {
		const reverse_routes = frappe.route_history.slice().reverse();
		let last_route = null;
		for (const route of reverse_routes) {
			if (route[0] === "Form" && route[1] === frm.doctype) continue;
			if (route[0] !== "Form") break; // stop at List or other non-Form routes
			last_route = route;
			break;
		}
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

function card_menu(frm, section, record, primary_name) {
	const { doctype } = section;
	return [
		{
			label: __("Edit"),
			icon: "pen",
			onclick: () => frappe.set_route("Form", doctype, record.name),
		},
		{
			label: __("Set as Primary"),
			icon: "star",
			condition: () => record.name !== primary_name,
			onclick: () => set_primary(frm, section, record),
		},
		{
			label: __("Unlink from {0}", [__(frm.doctype)]),
			icon: "unlink",
			onclick: () => delink_record(frm, doctype, record.name),
		},
		{
			label: __("Delete"),
			icon: "trash-2",
			theme: "red",
			onclick: () => delete_record(frm, doctype, record.name),
		},
	];
}

function get_primary_field(frm, doctype) {
	return (frm.meta.fields || []).find(
		(df) => df.fieldtype === "Link" && df.options === doctype && /primary/i.test(df.fieldname)
	)?.fieldname;
}

function get_primary_name(frm, section, records) {
	const primary_field = get_primary_field(frm, section.doctype);
	if (primary_field) return frm.doc[primary_field];
	return records.find((r) => r[section.primary_flag])?.name;
}

async function set_primary(frm, section, record) {
	const primary_field = get_primary_field(frm, section.doctype);

	if (primary_field) {
		await frappe.db.set_value(frm.doctype, frm.docname, primary_field, record.name);
	} else {
		await frappe.db.set_value(section.doctype, record.name, section.primary_flag, 1);
	}

	frm.reload_doc();
}

function delink_record(frm, doctype, name) {
	const label = `<b>${frappe.utils.escape_html(name)}</b>`;
	frappe.confirm(
		__("Unlink {0} {1} from {2}?", [__(doctype), label, __(frm.doctype)]),
		() => {
			frappe
				.xcall("frappe.contacts.address_and_contact.delink_party", {
					doctype,
					name,
					link_doctype: frm.doctype,
					link_name: frm.docname,
				})
				.then(() => {
					frappe.show_alert({
						message: __("{0} unlinked", [__(doctype)]),
						indicator: "green",
					});
					frm.reload_doc();
				});
		}
	);
}

function delete_record(frm, doctype, name) {
	const label = `<b>${frappe.utils.escape_html(name)}</b>`;
	frappe.confirm(__("Delete {0} {1}?", [__(doctype), label]), () => {
		frappe.db.delete_doc(doctype, name).then(() => {
			frappe.show_alert({ message: __("{0} deleted", [__(doctype)]), indicator: "green" });
			frm.reload_doc();
		});
	});
}
