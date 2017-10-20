// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Migration Connector', {
	refresh: function() {

	},
	new_connection(frm) {
		const d = new frappe.ui.Dialog({
			title: __('New Connection'),
			fields: [
				{ label: __('Module'), fieldtype: 'Link', options: 'Module Def', reqd: 1 },
				{ label: __('Connection Name'), fieldtype: 'Data', description: 'For e.g: Shopify Connection', reqd: 1 },
			],
			primary_action_label: __('Create'),
			primary_action: (values) => {
				let { module, connection_name } = values;

				frm.events.create_new_connection(frm, module, connection_name)
					.then(r => {
						if (r.message) {
							const connector_name = connection_name
								.replace('connection', 'Connector')
								.replace('Connection', 'Connector')
								.trim();

							frm.set_value('connector_name', connector_name);
							frm.set_value('is_custom', 1)
							frm.set_value('python_module', r.message);
							frm.save();
							frappe.show_alert(__(`New module created ${r.message}`));
							d.hide();
						}
					});
			}
		});

		d.show();

	},
	create_new_connection(frm, module, connection_name) {
		return frm.call('create_new_connection', {
			module, connection_name
		});
	}
});
