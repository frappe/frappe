frappe.listview_settings["DocType"] = {
	onload: function (me) {
		me.page.btn_primary.addClass("hidden");
		this.setup_select_primary_button(me);
	},

	setup_select_primary_button: function (me) {
		let actions = [
			{
				label: __("Add DocType"),
				description: __("Create a new DocType"),
				action: () => frappe.new_doc("DocType"),
			},
			{
				label: __("Add DocType (Form Builder)"),
				description: __("Use the form builder to create a new DocType"),
				action: () => frappe.set_route("form-builder", "new-doctype"),
			},
		];

		frappe.utils.add_select_group_button(
			me.page.btn_primary.parent(),
			actions,
			"btn-primary",
			"add"
		);
	},
};
