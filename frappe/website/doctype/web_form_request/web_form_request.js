// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Web Form Request", {
	refresh(frm) {
		// the server always sets it to the Web Form's doctype
		frm.fields_dict.references.grid.update_docfield_property("link_doctype", "read_only", 1);
		frm.trigger("set_reference_doctype");

		if (frm.is_new() || !frm.doc.key || !frm.doc.web_form) {
			return;
		}

		const references = (frm.doc.references || []).filter(
			(row) => row.link_name && !row.__islocal
		);
		if (!references.length) {
			frm.add_custom_button(__("Copy Link"), () => copy_link(frm));
			return;
		}

		frm.add_custom_button(__("New Response"), () => copy_link(frm), __("Copy Link"));
		for (const row of references) {
			frm.add_custom_button(
				row.link_name,
				() => copy_link(frm, row.link_name),
				__("Copy Link")
			);
		}
	},

	web_form(frm) {
		frm.trigger("set_reference_doctype");
	},

	async set_reference_doctype(frm) {
		frm.reference_doctype = null;
		if (!frm.doc.web_form) {
			return;
		}

		const web_form = frm.doc.web_form;
		const { message } = await frappe.db.get_value("Web Form", web_form, "doc_type");
		// web_form changed while waiting, a newer reply sets it
		if (frm.doc.web_form !== web_form) {
			return;
		}
		frm.reference_doctype = message.doc_type;
		for (const row of frm.doc.references || []) {
			if (row.link_doctype !== frm.reference_doctype) {
				frappe.model.set_value(
					row.doctype,
					row.name,
					"link_doctype",
					frm.reference_doctype
				);
			}
		}
	},
});

frappe.ui.form.on("Dynamic Link", {
	references_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "link_doctype", frm.reference_doctype);
	},
});

function copy_link(frm, docname) {
	const fields = ["route", "allow_edit"];
	frappe.db.get_value("Web Form", frm.doc.web_form, fields).then(({ message }) => {
		const route = message.route || frm.doc.web_form;
		let path = "new";
		if (docname) {
			// without /edit the portal opens the document read-only
			path = encodeURIComponent(docname) + (message.allow_edit ? "/edit" : "");
		}
		const key = encodeURIComponent(frm.doc.key);
		const url = frappe.urllib.get_full_url(`${route}/${path}?web_form_request_key=${key}`);
		frappe.utils.copy_to_clipboard(url, __("Web Form Request link copied"));
	});
}
