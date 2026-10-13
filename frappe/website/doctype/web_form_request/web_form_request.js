// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Web Form Request", {
	setup(frm) {
		$(frm.wrapper).on("grid-row-render", (e, grid_row) => {
			add_copy_link_button(frm, grid_row);
		});
	},

	refresh(frm) {
		// the server always sets it to the Web Form's doctype
		frm.fields_dict.references.grid.update_docfield_property("link_doctype", "read_only", 1);
		frm.trigger("set_reference_doctype");

		if (can_copy_link(frm)) {
			frm.add_custom_button(__("Copy New Response Link"), () => copy_link(frm));
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

function can_copy_link(frm) {
	return !frm.is_new() && frm.doc.key && frm.doc.web_form;
}

function add_copy_link_button(frm, grid_row) {
	const column = grid_row.columns.link_name;
	if (!column) {
		return;
	}

	// the grid reuses the cell on every render
	column.find(".copy-reference-link").remove();
	const row = grid_row.doc;
	if (!can_copy_link(frm) || !row.link_name || row.__islocal) {
		return;
	}

	const icon = frappe.utils.icon("link", "sm");
	$(`<button type="button" class="copy-reference-link grid-cell-action">${icon}</button>`)
		.attr({ title: __("Copy Link"), "aria-label": __("Copy Link") })
		.appendTo(column)
		.on("click", () => {
			if (frm.is_dirty()) {
				frappe.show_alert(__("Save the document to copy the link"));
			} else {
				copy_link(frm, row.link_name);
			}
			// the cell's own click opens the row for editing
			return false;
		});
}

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
