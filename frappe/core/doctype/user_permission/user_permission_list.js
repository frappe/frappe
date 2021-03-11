frappe.listview_settings['User Permission'] = {

	onload: function(list_view) {
		var me = this;
		list_view.page.add_inner_button( __("Add / Update"), function() {
			let dialog =new frappe.ui.Dialog({
				title : __('Add User Permissions'),
				fields: [
					{
						fieldname: 'user',
						label: __('For User'),
						fieldtype: 'Link',
						options: 'User',
						reqd: 1,
						onchange: function() {
							dialog.fields_dict.doctype.set_input(undefined);
							dialog.fields_dict.docname.set_input(undefined);
							dialog.set_df_property("docname", "hidden", 1);
							dialog.set_df_property("is_default", "hidden", 1);
							dialog.set_df_property("apply_to_all_doctypes", "hidden", 1);
							dialog.set_df_property("applicable_doctypes", "hidden", 1);
							dialog.set_df_property("hide_descendants", "hidden", 1);
						}
					},
					{
						fieldname: 'doctype',
						label: __('Document Type'),
						fieldtype: 'Link',
						options: 'DocType',
						reqd: 1,
						onchange: function() {
							me.on_doctype_change(dialog);
						}
					},
					{
						fieldname: 'docname',
						label: __('Document Name'),
						fieldtype: 'Dynamic Link',
						options: 'doctype',
						hidden: 1,
						onchange:  function() {
							let field = dialog.fields_dict["docname"];
							if(field.value != field.last_value) {
								if(dialog.fields_dict.doctype.value && dialog.fields_dict.docname.value && dialog.fields_dict.user.value){
									me.get_applicable_doctype(dialog).then(applicable => {
										me.get_multi_select_options(dialog, applicable).then(options => {
											me.applicable_options = options;
											me.on_docname_change(dialog, options, applicable);
											if(options.length > 5){
												dialog.fields_dict.applicable_doctypes.setup_select_all();
											}
										});
									});
								}
							}
						}
					},
					{
						fieldtype: "Section Break",
						hide_border: 1
					},
					{
						fieldname: 'is_default',
						label: __('Is Default'),
						fieldtype: 'Check',
						hidden: 1
					},
					{
						fieldname: 'apply_to_all_doctypes',
						label: __('Apply to all Documents Types'),
						fieldtype: 'Check',
						hidden: 1,
						onchange: function() {
							if(dialog.fields_dict.doctype.value && dialog.fields_dict.docname.value && dialog.fields_dict.user.value){
								me.on_apply_to_all_doctypes_change(dialog, me.applicable_options);
								if(me.applicable_options.length > 5){
									dialog.fields_dict.applicable_doctypes.setup_select_all();
								}
							}
						}
					},
					{
						fieldtype: "Column Break"
					},
					{
						fieldname: 'hide_descendants',
						label: __('Hide Descendants'),
						fieldtype: 'Check',
						hidden: 1
					},
					{
						fieldtype: "Section Break",
						hide_border: 1
					},
					{
						label: __("Applicable Document Types"),
						fieldname: "applicable_doctypes",
						fieldtype: "MultiCheck",
						options: [],
						columns: 2,
						hidden: 1
					},
				],
				primary_action: (data) => {
					data = me.validate(dialog, data);
					frappe.call({
						async: false,
						method: "frappe.core.doctype.user_permission.user_permission.add_user_permissions",
						args: {
							data : data
						},
						callback: function(r) {
							if(r.message === 1) {
								frappe.show_alert({message:__("User Permissions created sucessfully"), indicator:'blue'});
							} else {
								frappe.show_alert({message:__("Nothing to update"), indicator:'red'});

							}
						}
					});
					dialog.hide();
					list_view.refresh();
				},
				primary_action_label: __('Submit')
			});
			dialog.show();
		});
		list_view.page.add_inner_button( __("Bulk Delete"), function() {
			const dialog = new frappe.ui.Dialog({
				title: __('Clear User Permissions'),
				fields: [
					{
						fieldname: 'user',
						label: __('For User'),
						fieldtype: 'Link',
						options: 'User',
						reqd: 1
					},
					{
						fieldname: 'for_doctype',
						label: __('For Document Type'),
						fieldtype: 'Link',
						options: 'DocType',
						reqd: 1
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
								} else if(data === 1) {
									message = __('{0} record deleted', [data]);
								} else {
									message = __('{0} records deleted', [data]);
								}
								frappe.show_alert({
									message,
									indicator: 'info'
								});
								list_view.refresh();
							});
					});

				},
				primary_action_label: __('Delete')
			});

			dialog.show();
		});
	},

	validate: function(dialog, data) {
		if(dialog.fields_dict.applicable_doctypes.get_unchecked_options().length == 0) {
			data.apply_to_all_doctypes = 1;
			data.applicable_doctypes = [];
			return data;
		}
		if(data.apply_to_all_doctypes == 0 && !("applicable_doctypes" in data)) {
			frappe.throw(__("Please select applicable Doctypes"));
		}
		return data;
	},

	get_applicable_doctype: function(dialog) {
		return new Promise(resolve => {
			frappe.call({
				method: 'frappe.core.doctype.user_permission.user_permission.check_applicable_doc_perm',
				async: false,
				args:{
					user: dialog.fields_dict.user.value,
					doctype: dialog.fields_dict.doctype.value,
					docname: dialog.fields_dict.docname.value
				}
			}).then(r => {
				resolve(r.message);
			});
		});
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
				}
			}).then(r => {
				var options = [];
				for(var d in r.message){
					var checked = ($.inArray(d, applicable) != -1) ? 1 : 0;
					options.push({ "label":d, "value": d , "checked": checked});
				}
				resolve(options);
			});
		});
	},

	on_doctype_change: function(dialog) {
		dialog.set_df_property("docname", "hidden", 0);
		dialog.set_df_property("docname", "reqd", 1);
		dialog.set_df_property("is_default", "hidden", 0);
		dialog.set_df_property("apply_to_all_doctypes", "hidden", 0);
		dialog.set_value("apply_to_all_doctypes", "checked", 1);
		let show = frappe.boot.nested_set_doctypes.includes(dialog.get_value("doctype"));
		dialog.set_df_property("hide_descendants", "hidden", !show);
		dialog.refresh();
	},

	on_docname_change: function(dialog, options, applicable) {
		if(applicable.length != 0 ) {
			dialog.set_primary_action("Update");
			dialog.set_title("Update User Permissions");
			dialog.set_df_property("applicable_doctypes", "options", options);
			if(dialog.fields_dict.applicable_doctypes.get_checked_options().length == options.length) {
				dialog.set_df_property("applicable_doctypes", "hidden", 1);
			} else {
				dialog.set_df_property("applicable_doctypes", "hidden", 0);
				dialog.set_df_property("apply_to_all_doctypes", "checked", 0);
			}
		} else {
			dialog.set_primary_action("Submit");
			dialog.set_title("Add User Permissions");
			dialog.set_df_property("applicable_doctypes", "options", options);
			dialog.set_df_property("applicable_doctypes", "hidden", 1);
		}
		dialog.refresh();
	},

	on_apply_to_all_doctypes_change: function(dialog, options) {
		if(dialog.fields_dict.apply_to_all_doctypes.get_value() == 0) {
			dialog.set_df_property("applicable_doctypes", "hidden", 0);
			dialog.set_df_property("applicable_doctypes", "options", options);
		} else {
			dialog.set_df_property("applicable_doctypes", "options", options);
			dialog.set_df_property("applicable_doctypes", "hidden", 1);
		}
		dialog.refresh_sections();
	}
};
