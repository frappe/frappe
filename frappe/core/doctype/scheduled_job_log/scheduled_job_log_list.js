frappe.listview_settings["Scheduled Job Log"] = {
	onload: function (listview) {
		frappe.require("logtypes.bundle.js", () => {
			frappe.utils.logtypes.show_log_retention_message(cur_list.doctype);
		});
	},
};
