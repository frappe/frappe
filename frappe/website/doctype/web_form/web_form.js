frappe.web_form = {
	set_fieldname_select: function(frm) {
		return new Promise(resolve => {
			var me = this,
				doc = frm.doc;
			if (doc.doc_type) {
				frappe.model.with_doctype(doc.doc_type, function() {
					var fields = $.map(frappe.get_doc("DocType", frm.doc.doc_type).fields, function(d) {
						if (frappe.model.no_value_type.indexOf(d.fieldtype) === -1 ||
							d.fieldtype === 'Table') {
							return { label: d.label + ' (' + d.fieldtype + ')', value: d.fieldname };
						} else {
							return null;
						}
					});
					var currency_fields = $.map(frappe.get_doc("DocType", frm.doc.doc_type).fields, function(d) {
						if (d.fieldtype === 'Currency' || d.fieldtype === 'Float') {
							return { label: d.label, value: d.fieldname };
						} else {
							return null;
						}
					});
					frappe.meta.get_docfield("Web Form Field", "fieldname", frm.doc.name).options = [""].concat(fields);
					frappe.meta.get_docfield("Web Form", "amount_field", frm.doc.name).options = [""].concat(currency_fields);
					frm.refresh_field("amount_field");
					resolve();
				});
			}
		});
	}
};

frappe.ui.form.on("Web Form", {
	refresh: function(frm) {
		// show is-standard only if developer mode
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);

		frappe.web_form.set_fieldname_select(frm);

		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.set_read_only();
			frm.disable_save();
		}

		frm.add_custom_button(__('Get Fields'), () => {
			let webform_fieldtypes = frappe.meta.get_field('Web Form Field', 'fieldtype').options.split('\n');
			let fieldnames = (frm.doc.fields || []).map(d => d.fieldname);
			frappe.model.with_doctype(frm.doc.doc_type, () => {
				let meta = frappe.get_meta(frm.doc.doc_type);
				for (let field of meta.fields) {
					if (webform_fieldtypes.includes(field.fieldtype)
						&& !fieldnames.includes(field.fieldname)) {
						frm.add_child('web_form_fields', {
							fieldname: field.fieldname,
							label: field.label,
							fieldtype: field.fieldtype,
							options: field.options,
							reqd: field.reqd,
							default: field.default,
							read_only: field.read_only,
							depends_on: field.depends_on,
							hidden: field.hidden,
							description: field.description
						});
					}
				}
				frm.refresh();
			});
		});
	},

	title: function(frm) {
		if (frm.doc.__islocal) {
			var page_name = frm.doc.title.toLowerCase().replace(/ /g, "-");
			frm.set_value("route", page_name);
			frm.set_value("success_url", "/" + page_name);
		}
	},

	doc_type: function(frm) {
		frappe.web_form.set_fieldname_select(frm);
	}
});


frappe.ui.form.on("Web Form Field", {
	fieldtype: function(frm, doctype, name) {
		var doc = frappe.get_doc(doctype, name);
		if (['Section Break', 'Column Break', 'Page Break'].includes(doc.fieldtype)) {
			doc.fieldname = '';
			frm.refresh_field("web_form_fields");
		}
	},
	fieldname: function(frm, doctype, name) {
		var doc = frappe.get_doc(doctype, name);
		var df = $.map(frappe.get_doc("DocType", frm.doc.doc_type).fields, function(d) {
			return doc.fieldname == d.fieldname ? d : null;
		})[0];

		doc.label = df.label;
		doc.reqd = df.reqd;
		doc.options = df.options;
		doc.fieldtype = frappe.meta.get_docfield("Web Form Field", "fieldtype")
			.options.split("\n").indexOf(df.fieldtype) === -1 ? "Data" : df.fieldtype;
		doc.description = df.description;
		doc["default"] = df["default"];

	}
});
