// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Notification Log', {
	refresh: function(frm) {
		let dt = frm.doc.reference_doctype;
		let dn = frm.doc.reference_name;
		frm.fields_dict.reference_name.$input_wrapper.find('.control-value').wrapInner(`<a href='#Form/${dt}/${dn}'></a>`);
	}
});
