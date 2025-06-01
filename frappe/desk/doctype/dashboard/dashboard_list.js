nts.listview_settings["Dashboard"] = {
	button: {
		show(doc) {
			return doc.name;
		},
		get_label() {
			return nts.utils.icon("dashboard-list", "sm");
		},
		get_description(doc) {
			return __("View {0}", [`${doc.name}`]);
		},
		action(doc) {
			nts.set_route("dashboard-view", doc.name);
		},
	},
};
