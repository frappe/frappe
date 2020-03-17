// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Package Migration', {
	refresh: function(frm) {
		if (frm.doc.attach) {
			frm.add_custom_button(__("Connect"), function() {
				let dialog = new frappe.ui.Dialog({
					title: __('Connect to Remote Instance'),
					fields: [
						{
							fieldtype: 'Data',
							label: 'Remote Instance',
							fieldname: 'remote_instance',
							reqd: 1
						},
						{
							fieldtype: 'Data',
							label: 'User',
							fieldname: 'user',
							reqd: 1
						},
						{
							fieldtype: 'Password',
							label: 'Password',
							fieldname: 'password',
							reqd: 1
						},
					],
					primary_action: function() {
						let values = dialog.get_values();
						frm.call("install_package_to_remote", {
							"remote_instance": values.remote_instance,
							"user": values.user,
							"password": values.password
						}).then((r) => {
							console.log(r);
						})
						dialog.hide();
					},
					primary_action_label: "Execute"
				});
				dialog.show();
			})
		}
	}
});

// "erpnext_support_password": "uYrMeEhb2NzuEGOk",
//  "erpnext_support_url": "https://marketplace.erpnext.com",
//  "erpnext_support_user": "erpnext_support_fQrhUujW@erpnext.com",