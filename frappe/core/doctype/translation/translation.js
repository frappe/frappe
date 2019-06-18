// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt


frappe.ui.form.on('Translation', {
	refresh: function(frm) {
		if(frm.is_new() || !(["Saved", "Deleted"].includes(frm.doc.status))) return;
		frm.add_custom_button('Contribute', function() {
			frappe.call({
				method: 'frappe.core.doctype.translation.translation.contribute_translation',
				args: {
					"language": frm.doc.language,
					"contributor": frm.doc.owner,
					"source_name": frm.doc.source_name,
					"target_name": frm.doc.target_name,
					"doc_name": frm.doc.name
				}
			});
		}).addClass('btn-primary');
	}
});
