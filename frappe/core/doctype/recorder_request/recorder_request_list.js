frappe.listview_settings["Recorder Request"] = {
	hide_name_column: true,

	onload(listview) {
		listview.page.sidebar.remove();
		if (!has_common(frappe.user_roles, ["Administrator", "System Manager"])) return;

		frappe
			.xcall("frappe.core.doctype.recorder_request.recorder_request.get_status")
			.then((status) => {
				if (status) {
					listview.page.set_indicator(__("Active"), "green");
				} else {
					listview.page.set_indicator(__("Inactive"), "red");
				}
			});

		listview.page.add_button(__("Start"), () => {
			frappe.call({
				method: "frappe.core.doctype.recorder_request.recorder_request.start",
				callback: function () {
					listview.page.set_indicator(__("Active"), "green");
					listview.refresh();
				},
			});
		});

		listview.page.add_button(__("Stop"), () => {
			frappe.call({
				method: "frappe.core.doctype.recorder_request.recorder_request.stop",
				callback: function () {
					listview.page.set_indicator(__("Inactive"), "red");
					listview.refresh();
				},
			});
		});

		listview.page.add_button(__("Clear"), () => {
			frappe.call({
				method: "frappe.core.doctype.recorder_request.recorder_request.delete_requests",
				callback: function () {
					listview.refresh();
				},
			});
		});
	},
};
