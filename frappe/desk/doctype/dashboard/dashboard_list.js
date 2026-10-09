frappe.listview_settings["Dashboard"] = {
	button: {
		show(doc) {
			return doc.name;
		},
		get_label() {
			return frappe.utils.icon("layout-dashboard", "sm");
		},
		get_description(doc) {
			return __("View {0}", [`${doc.name}`]);
		},
		action(doc) {
			frappe.set_route("dashboard-view", doc.name);
		},
	},
};
