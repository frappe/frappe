frappe.listview_settings['User Permission'] = {
	onload: function(list_view) {
		list_view.page.add_inner_button(__("Clear User Permissions"), () => {
			const dialog = new frappe.ui.Dialog({
				title: 'Clear User Permissions',
				fields: [
					{
						'fieldname': 'user',
						'label': __('For User'),
						'fieldtype': 'Link',
						'options': 'User',
						'reqd': 1
					},
					{
						'fieldname': 'for_doctype',
						'label': __('For Document Type'),
						'fieldtype': 'Link',
						'options': 'DocType',
						'reqd': 1
					},
				],
				primary_action: (data) => {
					// mandatory not filled
					if (!data) return;

					frappe.confirm(__('Are you sure?'), () => {
						frappe
							.xcall('frappe.core.doctype.user_permission.user_permission.clear_user_permissions', data)
							.then((data) => {
								dialog.hide();
								frappe.show_alert({
									message: __('{0} records deleted', [data == '0' ? 'No': data]),
									indicator: 'green'
								});
								list_view.refresh();
							});
					});

				},
				primary_action_label: __('Clear')
			});

			dialog.show();
		});
	}
};
