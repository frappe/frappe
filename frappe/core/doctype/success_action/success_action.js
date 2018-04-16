// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Success Action', {
	on_load: (frm) => {
		if (!frm.action_multicheck) {
			frm.trigger('set_next_action_multicheck');
		}
	},
	refresh: (frm) => {
		if (!frm.action_multicheck) {
			frm.trigger('set_next_action_multicheck');
		}
	},
	validate: (frm) => {
		const checked_actions = frm.action_multicheck.get_checked_options();
		if (checked_actions.length < 2) {
			frappe.msgprint('Select atleast 2 actions');
		} else {
			return true;
		}
	},
	before_save: (frm) => {
		const checked_actions = frm.action_multicheck.get_checked_options();
		frm.doc.next_actions = checked_actions.join('\n');
	},
	after_save: (frm) => {
		frappe.boot.success_action.push(frm.doc); //needs refactor
	},
	set_next_action_multicheck: (frm) => {
		const next_actions_wrapper = frm.fields_dict.next_actions_html.$wrapper;
		const checked_actions = frm.doc.next_actions ? frm.doc.next_actions.split('\n') : [];
		const action_multicheck_options = ['New', 'Print', 'Email', 'List']
			.map(action => {
				return {
					label: action,
					value: action,
					checked: checked_actions.length ? checked_actions.includes(action) : 1
				};
			});
		frm.action_multicheck = frappe.ui.form.make_control({
			parent: next_actions_wrapper,
			df: {
				'label': 'Next Actions',
				'fieldname': 'next_actions_multicheck',
				'fieldtype': 'MultiCheck',
				'options': action_multicheck_options,
			},
		});
	}
});
