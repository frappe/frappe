// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Notification Log', {
	refresh: function(frm) {
		let dt = frm.doc.document_type;
		let dn = frm.doc.document_name;
		frm.fields_dict.document_name.$input_wrapper
			.find('.control-value')
			.wrapInner(`<a href='#Form/${dt}/${dn}'></a>`);
	}
});
