// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Assignment Rule', {
	refresh: function(frm) {
		// refresh description
		frm.events.rule(frm);
	},
	rule: function(frm) {
		if (frm.doc.rule === 'Round Robin') {
			frm.get_field('rule').set_description(__('Assign one by one, in sequence'));
		} else {
			frm.get_field('rule').set_description(__('Assign to the one who has the least assignments'));
		}
	}
});
