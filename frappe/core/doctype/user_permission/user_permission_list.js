frappe.listview_settings['User Permission'] = {

	onload: function(list_view) {
		var me =this
		list_view.page.add_menu_item(__("Create/Update User Permissions"), function() {
			var dialog =new frappe.ui.Dialog({
				title : __('Add User Permissions'),
				fields: [
					{
						'fieldname': 'user',
						'label': __('For User'),
						'fieldtype': 'Link',
						'options': 'User',
						'reqd': 1,
					},
					{
						'fieldname': 'doctype',
						'label': __('Document Type'),
						'fieldtype': 'Link',
						'options': 'DocType',
						'reqd': 1,
						'onchange': function() {
							var options = []
							if(dialog.fields_dict.doctype.value){
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
							}
							dialog.set_df_property("docname", "options", options)
							dialog.set_df_property("docname", "hidden", 0)
							dialog.set_df_property("docname", "reqd", 1)
							dialog.set_df_property("apply_to_all_doctypes", "hidden", 0)
							dialog.set_value("apply_to_all_doctypes","checked",1)
						}
					},
					{
						'fieldname': 'docname',
						'label': __('Document Name'),
						'fieldtype': 'Select',
						'hidden': 1,
						'onchange':  function(){
							me.get_applicable_doctype(dialog).then(applicable => {
								me.get_multi_select_options(dialog, applicable).then(options =>{
								if (options.length == applicable.length){
									console.log("inside if")
									dialog.set_primary_action("Update")
									dialog.set_title("Update User Permissions")
									dialog.set_value("apply_to_all_doctypes", "checked",1)
									dialog.set_df_property("applicable_doctypes", "options", options)
									dialog.set_df_property("applicable_doctypes", "hidden", 1)
								}else if(applicable.length != 0 ){
									console.log("inside elseif")
									dialog.set_primary_action("Update")
									dialog.set_title("Update User Permissions")
									dialog.set_df_property("apply_to_all_doctypes", "checked", 0)
									dialog.set_df_property("applicable_doctypes", "hidden", 0)
									dialog.set_df_property("applicable_doctypes", "options", options)
								}else{
									console.log("inside else")
									dialog.set_value("apply_to_all_doctypes", "checked",1)
									dialog.set_df_property("applicable_doctypes", "options", options)
									dialog.set_df_property("applicable_doctypes", "hidden", 1)
								}
							})
							})
						}
					},
					{
						'fieldname': 'apply_to_all_doctypes',
						'label': __('Apply to all Doctypes'),
						'fieldtype': 'Check',
						'checked': 1,
						'hidden': 1,
						'onchange': function() {
							if(dialog.fields_dict.doctype.value && dialog.fields_dict.docname.value && dialog.fields_dict.user.value){
								me.get_applicable_doctype(dialog).then(applicable => {
									me.get_multi_select_options(dialog, applicable).then(options =>{
									if(dialog.fields_dict.apply_to_all_doctypes.get_value() == 0){
										dialog.set_df_property("applicable_doctypes", "hidden", 0)
										dialog.set_df_property("applicable_doctypes", "options", options)
									}else{
										dialog.set_df_property("applicable_doctypes", "hidden", 1)
										dialog.set_df_property("applicable_doctypes", "options", options)
									}
								})
							})
						}
					}
					},
					{
						"label": __("Applicable Doctypes"),
						"fieldname": "applicable_doctypes",
						"fieldtype": "MultiCheck",
						"options": [],
						"columns": 2,
						"hidden": 1
					},
				],
				primary_action: (data) => {
						if(dialog.fields_dict.applicable_doctypes.get_unchecked_options().length == 0){
							data.apply_to_all_doctypes = 1
							data.applicable_doctypes = []
						}
						frappe.call({
							async: false,
							method: "frappe.core.doctype.user_permission.user_permission.add_user_permissions",
							args: {
								data : data
							},
							callback: function(r){
								if (r.message == 1){
									frappe.show_alert({message:__("User Permissions Created Sucessfully"), indicator:'blue'});
								}else{
									frappe.show_alert({message:__("User Permissions Not Created"), indicator:'red'});

								}
							}
						})
					dialog.hide();
					list_view.refresh();
				},
				primary_action_label: __('Submit')
			});
			dialog.show();
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
	},

	get_applicable_doctype: function(dialog){
		return new Promise(resolve => {
			frappe.call({
				method: 'frappe.core.doctype.user_permission.user_permission.check_applicable_doc_perm',
				async: false,
				args:{
					user: dialog.fields_dict.user.value,
					doctype: dialog.fields_dict.doctype.value,
					docname: dialog.fields_dict.docname.value
				}}).then(r => {
					resolve(r.message)
				})
		})
	},

	get_multi_select_options: function(dialog, applicable){
		return new Promise(resolve => {
			frappe.call({
				method: 'frappe.desk.form.linked_with.get_linked_doctypes',
				async: false,
				args:{
					user: dialog.fields_dict.user.value,
					doctype: dialog.fields_dict.doctype.value,
					docname: dialog.fields_dict.docname.value
				}}).then(r => {
					var options = []
					for(var d in r.message){
						var checked = ($.inArray(d, applicable) != -1) ? 1 : 0;
						options.push({ "label":d, "value": d , "checked": checked})
					}
					resolve(options)
				})
		})
	}

};
