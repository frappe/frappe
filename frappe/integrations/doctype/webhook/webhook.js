// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.webhook = {
	set_fieldname_select: (frm) => {
		if (frm.doc.webhook_doctype) {
			frappe.model.with_doctype(frm.doc.webhook_doctype, () => {
				// get doctype fields
				let fields = $.map(frappe.get_doc("DocType", frm.doc.webhook_doctype).fields, (d) => {
					if (frappe.model.no_value_type.indexOf(d.fieldtype) === -1 || d.fieldtype === 'Table') {
						return { label: d.label + ' (' + d.fieldtype + ')', value: d.fieldname };
					} else if (d.fieldtype === 'Currency' || d.fieldtype === 'Float') {
						return { label: d.label, value: d.fieldname };
					} else {
						return null;
					}
				});

				// add meta fields
				for (let field of frappe.model.std_fields) {
					if (field.fieldname == "name") {
						fields.unshift({ label: "Name (Doc Name)", value: "name" });
					} else {
						fields.push({ label: field.label + ' (' + field.fieldtype + ')', value: field.fieldname });
					}
				}

				frappe.meta.get_docfield("Webhook Data", "fieldname", frm.doc.name).options = [""].concat(fields);
			});
		}
	}
};

frappe.ui.form.on('Webhook', {
	refresh: (frm) => {
		frappe.webhook.set_fieldname_select(frm);
	},

	webhook_doctype: (frm) => {
		frappe.webhook.set_fieldname_select(frm);
	}
});

frappe.ui.form.on("Webhook Data", {
	fieldname: (frm, cdt, cdn) => {
		let row = locals[cdt][cdn];
		let df = frappe.get_meta(frm.doc.webhook_doctype).fields.filter((field) => field.fieldname == row.fieldname);

		if (!df.length) {
			// check if field is a meta field
			df = frappe.model.std_fields.filter((field) => field.fieldname == row.fieldname);
		}

		row.key = df.length ? df[0].fieldname : "name";
		frm.refresh_field("webhook_data");
	}
});
