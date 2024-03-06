frappe.listview_settings["Module Def"] = {
	onload: function (list_view) {
		frappe.call({
			method: "frappe.core.doctype.module_def.module_def.get_installed_apps",
			callback: (r) => {
				const field = list_view.page.fields_dict.app_name;
				if (!field) return;

				const options = JSON.parse(r.message);
				options.unshift(""); // Add empty option
				field.df.options = options;
				field.set_options();
			},
		});
	},
};
