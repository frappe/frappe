// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt
frappe.web_form = {
	set_fields_table: function(frm, mandatory=false) {
		let ref_doc = frm.doc.reference_doctype;

		// Throw an error if refernce doctype is not set
		if (!ref_doc) {
			frappe.throw({
				message: "Please select a Reference Doctype",
				title: "Mandatory Error"
			});
		}

		frappe.model.with_doctype(ref_doc, () => {
			// Get reference doctype meta
			let meta = frappe.get_meta(ref_doc);
			let valid_fieldtypes = frappe.meta.get_field('Web Form Field', 'fieldtype').options.split('\n');
			let fieldnames = (frm.doc.fields || []).map(d => d.fieldname);

			// get fields to be added to Fields
			let fields = meta.fields
			if (mandatory) fields = fields.filter(df => df.reqd) // Check mandatory

			fields.forEach(field => {
				if (valid_fieldtypes.includes(field.fieldtype) && !fieldnames.includes(field.fieldname)) {
					// Append to Fields Child Table
					frm.add_child('fields', field);
				}
			})
			frm.refresh();
		});
	},

	set_fieldname_select: function(frm) {
		let ref_doc = frm.doc.reference_doctype;

		// Throw an error if refernce doctype is not set
		if (!ref_doc) {
			frappe.throw({
				message: "Please select a Reference Doctype",
				title: "Mandatory Error"
			});
		}

		const non_data_fields = ["Section Break", "Column Break"]

		frappe.model.with_doctype(ref_doc, () => {
			let meta = frappe.get_meta(ref_doc);
			let fields = meta.fields.filter(df => !non_data_fields.includes(df.fieldtype))
			let options = fields.map(df => {
				return { label: df.label + ' (' + df.fieldtype + ')', value: df.fieldname };
			})

			frappe.meta.get_docfield("Web Form Field", "fieldname", frm.doc.name).options = [""].concat(options);
		})
	}
};


frappe.ui.form.on('Web Form Beta', {
	refresh: function(frm) {
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);
		frm.set_value("reference_doctype", "Note")
		frappe.web_form.set_fieldname_select(frm);

		frm.add_custom_button(__('Get All Fields'), () => {
			frappe.web_form.set_fields_table(frm)
		});

		frm.add_custom_button(__('Get Mandatory Fields'), () => {
			frappe.web_form.set_fields_table(frm, true)
		});
	},

	title: function(frm) {
		if (frm.doc.__islocal) {
			var page_name = frm.doc.title.toLowerCase().replace(/ /g, "-");
			frm.set_value("route", page_name);
			frm.set_value("success_url", "/" + page_name);
		}
	},

	reference_doctype: function(frm) {
		frappe.web_form.set_fieldname_select(frm);
	}
});

frappe.ui.form.on("Web Form Field", {
	fieldtype: function(frm, doctype, name) {
		var doc = frappe.get_doc(doctype, name);
		if (['Section Break', 'Column Break'].includes(doc.fieldtype)) {
			doc.fieldname = '';
			frm.refresh_field("fields");
		}
	},

	fieldname: function(frm, doctype, name) {
		window.frm = frm
	}
});

