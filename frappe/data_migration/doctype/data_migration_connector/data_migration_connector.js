// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Migration Connector', {
	onload(frm) {
		if(frappe.boot.developer_mode) {
			frm.add_custom_button(__('New Connection'), () => frm.events.new_connection(frm));
		}
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

				frm.events.create_new_connection(module, connection_name)
					.then(r => {
						if (r.message) {
							const connector_name = connection_name
								.replace('connection', 'Connector')
								.replace('Connection', 'Connector')
								.trim();

							frm.set_value('connector_name', connector_name);
							frm.set_value('connector_type', 'Custom');
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
	create_new_connection(module, connection_name) {
		return frappe.call('frappe.data_migration.doctype.data_migration_connector.data_migration_connector.create_new_connection', {
			module, connection_name
		});
	}
});
