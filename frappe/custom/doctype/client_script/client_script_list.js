frappe.listview_settings["Client Script"] = {
	// Runs after the list has loaded its meta; the filter popover copies these options when a row is built.
	refresh() {
		if (cint(frappe.boot.sysdefaults.enable_desk_v2)) return;
		// Record, App Page and List Page scripts run only in desk v2.
		frappe.meta.get_docfield("Client Script", "view").options = "List\nForm";
	},
};
