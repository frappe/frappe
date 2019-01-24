frappe.listview_settings['User Permission'] = {
	onload: function(list_view) {
		list_view.page.add_menu_item(__("Add User Permissions"), function() {
			var dialog =new frappe.ui.Dialog({
				title : __('Add User Permissions'),
				fields: [
					{
						'fieldname': 'user',
						'label': __('For User'),
						'fieldtype': 'Link',
						'options': 'User',
						'reqd': 1
					},
					{
						'fieldname': 'doctype',
						'label': __('Document Type'),
						'fieldtype': 'Link',
						'options': 'DocType',
						'reqd': 1,
						'onchange': function() {
							dialog.set_df_property("docname", "get_data", function(){
								var options = []
								frappe.call({
									method:"frappe.client.get_list",
									async: false,
									args: {
										doctype: dialog.fields_dict.doctype.value,
									},
									callback: function(r) {
										for(var d in r.message){
											options.push(r.message[d].name)
										}
									}
								});
								return options
							})
						}
					},
					{
						'fieldname': 'docname',
						'label': __('Document Name'),
						'fieldtype': 'MultiSelect',
						'reqd': 1,
					},
					{
						'fieldname': 'apply_to_all_doctypes',
						'label': __('Apply to all Doctypes'),
						'fieldtype': 'Check',
						'default': 1,
						'onchange': function() {
							if(dialog.fields_dict.apply_to_all_doctypes.get_value() == 0){
								frappe.call({
									method:'frappe.desk.form.linked_with.get_linked_doctypes',
									async: false,
									args: {
										doctype: dialog.fields_dict.doctype.value,
									},
									callback: function(r) {
										var options = []
										for(var d in r.message){
											options.push({ "label":d, "value": d })
										}
										dialog.set_df_property("aplicable_doctypes", "options", options)
									}
								});
							}else{
								dialog.set_df_property("aplicable_doctypes", "options", undefined)
							}
						}
					},
					{
						"label": "Aplicable Doctypes",
						"fieldname": "aplicable_doctypes",
						"fieldtype": "MultiCheck",
						"columns": 2
					},
				],
				primary_action: (data) => {
					dialog.hide()
				},
				primary_action_label: __('Submit')
			});
			dialog.show();
			dialog
		});

		list_view.page.add_menu_item(__("Clear User Permissions"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __('Clear User Permissions'),
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
							.then(data => {
								dialog.hide();
								let message = '';
								if (data === 0) {
									message = __('No records deleted');
								} else {
									message = __('{0} records deleted', [data]);
								}
								frappe.show_alert({
									message,
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
