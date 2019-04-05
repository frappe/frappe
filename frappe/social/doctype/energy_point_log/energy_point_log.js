// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Energy Point Log', {
	refresh: function(frm) {
		if (frm.doc.reverted) {
			frm.set_intro(__('This document has been reverted'));
		} else if (!['Revert', 'Review'].includes(frm.doc.type)
			&& frappe.user_roles.includes('System Manager')) {
			const revert_button = __('Revert');
			frm.add_custom_button(revert_button, () => {
				return frappe.xcall('frappe.social.doctype.energy_point_log.energy_point_log.revert', {
					'name': frm.doc.name
				});
			});
		}
	}
});
