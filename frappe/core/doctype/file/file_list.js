frappe.listview_settings["File"] = {
	formatters: {
		file_name: function (value) {
			return frappe.utils.escape_html(value || "");
		},
	},
};
