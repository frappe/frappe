// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Installed Applications", {
	refresh: function (frm) {
		frm.add_custom_button(__("Update Hooks Resolution Order"), () => {
			frm.trigger("show_update_order_dialog");
		});
	},

	show_update_order_dialog() {
		const dialog = new frappe.ui.Dialog({
			title: __("Update Hooks Resolution Order"),
			fields: [
				{
					fieldname: "apps",
					fieldtype: "Table",
					label: __("Installed Apps"),
					cannot_add_rows: true,
					cannot_delete_rows: true,
					in_place_edit: true,
					data: [],
					fields: [
						{
							fieldtype: "Data",
							fieldname: "app_name",
							label: __("App Name"),
							in_list_view: 1,
							read_only: 1,
						},
					],
				},
			],
			primary_action: function () {
				const new_order = this.get_values()["apps"].map((row) => row.app_name);
				frappe.call({
					method: "frappe.core.doctype.installed_applications.installed_applications.update_installed_apps_order",
					freeze: true,
					args: {
						new_order: new_order,
					},
				});
				this.hide();
			},
			primary_action_label: __("Update Order"),
		});

		frappe
			.xcall(
				"frappe.core.doctype.installed_applications.installed_applications.get_installed_app_order"
			)
			.then((data) => {
				data.forEach((app) => {
					dialog.fields_dict.apps.df.data.push({
						app_name: app,
					});
				});

				dialog.fields_dict.apps.grid.refresh();
				// hack: change checkboxes to drag handles.
				let grid = $(dialog.fields_dict.apps.grid.parent);
				grid.find(".grid-row-check:first").remove() &&
					grid.find(".grid-row-check").replaceWith(frappe.utils.icon("menu"));
				dialog.show();
			});
	},
});
