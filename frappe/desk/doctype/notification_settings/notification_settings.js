// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Notification Settings', {
	onload: () => {
		frappe.breadcrumbs.add({
			label: __('Settings'),
			route: '#modules/Settings',
			type: 'Custom'
		});
	},

	refresh: (frm) => {
		if (frappe.user.has_role('System Manager')) {
			frm.add_custom_button('Go to Notification Settings List', () => {
				frappe.set_route('List', 'Notification Settings');
			});
		}
	}

});
