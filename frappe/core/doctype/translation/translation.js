// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt


frappe.ui.form.on('Translation', {
	before_load: function(frm) {
		frappe.setup_language_field(frm);
	},
	language: function(frm) {
		frm.events.update_language_code(frm);
	},
	validate: function(frm) {
		if(!frm.doc.language_code){
			frm.events.update_language_code(frm)
		}
	},
	update_language_code: function(frm){
		frm.set_value('language_code', frm.doc.language)
	}
});

