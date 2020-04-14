// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Onboarding Slide', {
	refresh: function(frm) {
		frm.toggle_reqd('ref_doctype', (frm.doc.slide_type=='Create' || frm.doc.slide_type=='Settings'));
		frm.toggle_reqd('slide_module', (frm.doc.slide_type=='Information' || frm.doc.slide_type=='Continue'));
		if (frm.doc.ref_doctype) frm.trigger('ref_doctype');
	},

	ref_doctype: function(frm) {
		frm.set_query('ref_doctype', function() {
			if (frm.doc.slide_type === 'Create') {
				return {
					filters: {
						'issingle': 0,
						'istable': 0
					}
				};
			} else if (frm.doc.slide_type === 'Settings') {
				return {
					filters: {
						'issingle': 1,
						'istable': 0
					}
				};
			}
		});

		//fetch mandatory fields automatically
		if (frm.doc.ref_doctype) {
			const ref = frm.doc.ref_doctype
			frappe.model.with_doctype(ref, function() {
				const meta = frappe.get_meta(ref)
				const fields = meta.fields.filter(
					df => !frappe.model.no_value_type.includes(df.fieldtype)
				).map(df => {
					return { label: `${df.label} (${df.fieldtype})`, value: df.fieldname }
				});

				frappe.meta.get_docfield("Onboarding Slide Field", "fieldname", frm.doc.name).options = [""].concat(fields);
				refresh_field('slide_fields');
			});
		}
	}
});

frappe.ui.form.on("Onboarding Slide Field", {
	fieldtype: function(frm, doctype, name) {
		var doc = frappe.get_doc(doctype, name);
		if (['Section Break', 'Column Break', 'Page Break'].includes(doc.fieldtype)) {
			doc.fieldname = '';
			frm.refresh_field("slide_fields");
		}
	},
	fieldname: function(frm, doctype, name) {
		var doc = frappe.get_doc(doctype, name);
		const ref = frm.doc.ref_doctype;
		frappe.model.with_doctype(ref, function() {
			const meta = frappe.get_meta(ref)
			const fields = meta.fields.filter(df => doc.fieldname == df.fieldname);

			if (fields.length) {
				let df = fields[0];

				doc.label = df.label;
				doc.reqd = df.reqd;
				doc.options = df.options;
				doc.fieldtype = df.fieldtype;
			}
			refresh_field('slide_fields');
		});
	}
});

