// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Energy Point Log', {
	refresh: function(frm) {
		if (frm.doc.reverted) {
			frm.set_intro(__('This document has been reverted'));
		} else if (!['Revert', 'Review'].includes(frm.doc.type)
			&& frappe.user_roles.includes('System Manager')) {
			frm.add_custom_button(__('Revert'), () => frm.events.show_revert_dialog(frm));
		}
	},
	show_revert_dialog(frm) {
		const revert_dialog = new frappe.ui.Dialog({
			title: __('Revert'),
			fields: [{
				fieldname: 'reason',
				fieldtype: 'Small Text',
				label: __('Reason'),
				reqd: 1
			}],
			primary_action: (values) => {
				return frappe.xcall('frappe.social.doctype.energy_point_log.energy_point_log.revert', {
					'name': frm.doc.name,
					'reason': values.reason
				}).then(revert_log => {
					revert_dialog.hide();
					revert_dialog.clear();
					frappe.model.docinfo[frm.doc.reference_doctype][frm.doc.reference_name].energy_point_logs.unshift(revert_log);
				}).catch(() => {});
			},
			primary_action_label: __('Submit')
		});
		revert_dialog.show();
	}
});
